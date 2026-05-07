from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone

from hospitals.models import Patient, MedicalRecordMeta, NurseQueueItem
from hospitals.permissions import IsDoctor
from auditlog.utils import log_action
from .services import service_predict_ckd


@api_view(['POST'])
@permission_classes([IsDoctor])
def predict_ckd(request):
    """
    POST /api/ml/predict/ckd/
    Body: { "patient_id": "<uuid>", "record_id": "<uuid>" }
    Only doctors can call this endpoint.
    """
    patient_id = request.data.get('patient_id', '').strip()
    record_id  = request.data.get('record_id', '').strip()

    if not patient_id:
        return Response({'error': 'patient_id is required'}, status=400)
    if not record_id:
        return Response({'error': 'record_id is required'}, status=400)

    # verify patient exists
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    # fetch the latest version of the KFT record
    meta = (
        MedicalRecordMeta.objects
        .filter(record_id=record_id, patient_id=patient_id)
        .order_by('-version')
        .first()
    )
    if not meta:
        return Response({'error': 'KFT record not found for this patient'}, status=404)

    # confirm the record is from a CKD/KFT lab
    if meta.lab_request and meta.lab_request.lab:
        if meta.lab_request.lab.lab_type != 'ckd':
            return Response(
                {'error': 'This record is not from a CKD/KFT lab. Prediction requires a KFT report.'},
                status=400,
            )

    # get most recent nurse vitals for blood pressure
    nurse_item = (
        NurseQueueItem.objects
        .filter(patient_id=patient_id)
        .exclude(blood_pressure__isnull=True)
        .exclude(blood_pressure='')
        .order_by('-created_at')
        .first()
    )
    bp_string = nurse_item.blood_pressure if nurse_item else None

    # run prediction
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
        )
        return Response({'error': error}, status=500)

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
    )

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
        'predicted_by':        request.user_payload.get('staff_id'),
        'predicted_at':        timezone.now().isoformat(),
    }, status=200)