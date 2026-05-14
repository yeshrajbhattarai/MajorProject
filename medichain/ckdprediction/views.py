
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
import uuid

from hospitals.models import Patient, MedicalRecordMeta, NurseQueueItem
from hospitals.permissions import IsDoctor
from auditlog.utils import log_action
from .services import service_predict_ckd


@api_view(['POST'])
@permission_classes([IsDoctor])
def predict_ckd(request):
    """
    POST /api/ml/predict/ckd/
    
    Body:
    {
        "patient_id": "<uuid>",
        "record_id": "<uuid>"
    }
    
    Only doctors (staff_role: 'doctor') can call this endpoint.
    
    Returns:
    {
        "patient_id": "<uuid>",
        "patient_name": "Dr. Name",
        "record_id": "<uuid>",
        "prediction": "CKD" | "Not CKD",
        "prediction_code": 0 | 1,
        "confidence": 87.5,
        "ckd_probability": 87.5,
        "not_ckd_probability": 12.5,
        "risk_level": "High" | "Moderate" | "Low-Moderate" | "Low",
        "suggested_action": "Immediate nephrology referral...",
        "imputed_fields": ["field1", "field2"],
        "predicted_by": "<staff_id>",
        "predicted_at": "2024-01-15T10:30:00Z"
    }
    """
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 1: VALIDATE REQUEST PARAMETERS
    # ═════════════════════════════════════════════════════════════════════
    
    patient_id = request.data.get('patient_id', '').strip()
    record_id = request.data.get('record_id', '').strip()
    
    if not patient_id:
        return Response(
            {'error': 'patient_id is required'},
            status=400
        )
    
    if not record_id:
        return Response(
            {'error': 'record_id is required'},
            status=400
        )
    
    # Validate UUIDs
    try:
        uuid.UUID(patient_id)
        uuid.UUID(record_id)
    except ValueError:
        return Response(
            {'error': 'patient_id and record_id must be valid UUIDs'},
            status=400
        )
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 2: VERIFY PATIENT EXISTS
    # ═════════════════════════════════════════════════════════════════════
    
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        log_action(
            'CKD_PREDICTION_FAILED',
            request.user_payload.get('staff_id'),
            record_id,
            extra_info='Patient not found',
        )
        return Response(
            {'error': f'Patient {patient_id} not found'},
            status=404
        )
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 3: FETCH THE LATEST VERSION OF THE KFT RECORD
    # ═════════════════════════════════════════════════════════════════════
    
    meta = (
        MedicalRecordMeta.objects
        .filter(record_id=record_id, patient_id=patient_id)
        .order_by('-version')
        .first()
    )
    
    if not meta:
        log_action(
            'CKD_PREDICTION_FAILED',
            request.user_payload.get('staff_id'),
            record_id,
            extra_info='KFT record not found for patient',
            scope_hospitals=[],
        )
        return Response(
            {'error': f'KFT record {record_id} not found for patient {patient_id}'},
            status=404
        )
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 4: VERIFY RECORD IS FROM A CKD/KFT LAB
    # ═════════════════════════════════════════════════════════════════════
    
    if meta.lab_request and meta.lab_request.lab:
        if meta.lab_request.lab.lab_type != 'ckd':
            log_action(
                'CKD_PREDICTION_FAILED',
                request.user_payload.get('staff_id'),
                record_id,
                extra_info=f"Record from non-CKD lab: {meta.lab_request.lab.lab_type}",
                scope_hospitals=[meta.hospital.hospital_name],
            )
            return Response(
                {
                    'error': (
                        'This record is not from a CKD/KFT lab. '
                        'Prediction requires a KFT report.'
                    )
                },
                status=400,
            )
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 5: FETCH MOST RECENT NURSE VITALS FOR BLOOD PRESSURE
    # ═════════════════════════════════════════════════════════════════════
    
    nurse_item = (
        NurseQueueItem.objects
        .filter(patient_id=patient_id)
        .exclude(blood_pressure__isnull=True)
        .exclude(blood_pressure='')
        .order_by('-created_at')
        .first()
    )
    
    bp_string = nurse_item.blood_pressure if nurse_item else None
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 6: RUN PREDICTION
    # ═════════════════════════════════════════════════════════════════════
    
    result, error = service_predict_ckd(
        raw_values=meta.custom_field_values or {},
        bp_string=bp_string,
    )
    
    if error:
        log_action(
            'CKD_PREDICTION_FAILED',
            request.user_payload.get('staff_id'),
            record_id,
            extra_info=error,
            scope_hospitals=[meta.hospital.hospital_name],
        )
        return Response(
            {'error': f'Prediction failed: {error}'},
            status=500
        )
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 7: LOG SUCCESS
    # ═════════════════════════════════════════════════════════════════════
    
    log_action(
        'CKD_PREDICTION_SUCCESS',
        request.user_payload.get('staff_id'),
        record_id,
        extra_info=(
            f"Patient: {patient.full_name} | "
            f"Result: {result['prediction']} | "
            f"Confidence: {result['confidence']}% | "
            f"Risk: {result['risk_level']}"
        ),
        scope_hospitals=[meta.hospital.hospital_name],
    )
    
    # ═════════════════════════════════════════════════════════════════════
    # STEP 8: RETURN RESPONSE
    # ═════════════════════════════════════════════════════════════════════
    
    return Response({
        'patient_id':          str(patient.id),
        'patient_name':        patient.full_name,
        'record_id':           str(meta.record_id),
        'prediction':          result['prediction'],
        'prediction_code':     result['prediction_code'],
        'confidence':          result['confidence'],
        'ckd_probability':     result['ckd_probability'],
        'not_ckd_probability': result['not_ckd_probability'],
        'risk_level':          result['risk_level'],
        'suggested_action':    result['suggested_action'],
        'imputed_fields':      result['imputed_fields'],
        'predicted_by':        str(request.user_payload.get('staff_id')),
        'predicted_at':        timezone.now().isoformat(),
    }, status=200)