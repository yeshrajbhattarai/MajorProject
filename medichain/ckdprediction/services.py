import json
import pickle
import numpy as np
import os

# load all model files once at startup — not on every request
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'ckd_model_final.pkl'), 'rb') as f:
    _MODEL = pickle.load(f)

with open(os.path.join(BASE_DIR, 'ckd_scaler.pkl'), 'rb') as f:
    _SCALER = pickle.load(f)

with open(os.path.join(BASE_DIR, 'ckd_imputation_values.json')) as f:
    _IMPUTATION = json.load(f)

with open(os.path.join(BASE_DIR, 'ckd_encoding_maps.json')) as f:
    _ENCODING = json.load(f)

with open(os.path.join(BASE_DIR, 'ckd_feature_columns.json')) as f:
    _FEATURE_COLUMNS = json.load(f)

_CATEGORICAL_COLS = list(_ENCODING.keys())
_NUMERICAL_COLS = [col for col in _FEATURE_COLUMNS if col not in _CATEGORICAL_COLS]


def _parse_bp(bp_value):
    # nurse stores BP as "120/80" — UCI dataset uses diastolic (second number)
    if not bp_value:
        return None
    try:
        parts = str(bp_value).strip().split('/')
        if len(parts) == 2:
            return float(parts[1])
        return float(parts[0])
    except (ValueError, IndexError):
        return None


def _get_risk_level(confidence, prediction):
    # maps prediction + confidence to risk label and clinical action
    if prediction == 1:
        if confidence >= 0.85:
            return 'High', 'Immediate nephrology referral recommended. Begin CKD management protocol.'
        elif confidence >= 0.65:
            return 'Moderate', 'Further diagnostic tests recommended. Schedule follow-up within 2 weeks.'
        else:
            return 'Low-Moderate', 'Borderline result. Repeat KFT in 4 weeks and monitor symptoms.'
    else:
        if confidence >= 0.85:
            return 'Low', 'No indicators of CKD detected. Routine follow-up as scheduled.'
        else:
            return 'Low-Moderate', 'Result is negative but confidence is low. Repeat KFT in 4 weeks.'


def service_predict_ckd(raw_values: dict, bp_string: str = None):
    """
    Builds feature vector from KFT lab values and runs CKD prediction.
    Returns (result_dict, error_string).
    """
    features = {}

    # step 1 — fill everything with imputation defaults
    for col in _FEATURE_COLUMNS:
        features[col] = _IMPUTATION.get(col)

    # step 2 — override with actual values from the KFT report
    for col in _FEATURE_COLUMNS:
        val = raw_values.get(col)
        if val is not None and str(val).strip() not in ('', 'None'):
            features[col] = val

    # step 3 — parse blood pressure from nurse vitals string
    parsed_bp = _parse_bp(bp_string)
    if parsed_bp is not None:
        features['bp'] = parsed_bp

    # step 4 — encode categorical features using training encoding maps
    for col in _CATEGORICAL_COLS:
        raw = str(features.get(col, '')).strip().lower()
        mapping = _ENCODING.get(col, {})
        if raw in mapping:
            features[col] = mapping[raw]
        else:
            default_raw = str(_IMPUTATION.get(col, '')).strip().lower()
            features[col] = mapping.get(default_raw, 0)

    # step 5 — convert numerical features to float
    for col in _NUMERICAL_COLS:
        try:
            features[col] = float(features[col])
        except (TypeError, ValueError):
            features[col] = float(_IMPUTATION.get(col, 0))

    # step 6 — build feature vector in exact training column order
    try:
        feature_vector = np.array([[features[col] for col in _FEATURE_COLUMNS]])
    except KeyError as e:
        return None, f"Missing feature: {e}"

    # step 7 — scale using the scaler fitted during training
    feature_vector_scaled = _SCALER.transform(feature_vector)

    # step 8 — predict
    prediction = int(_MODEL.predict(feature_vector_scaled)[0])
    probabilities = _MODEL.predict_proba(feature_vector_scaled)[0]
    confidence = float(probabilities[prediction])

    risk_level, suggested_action = _get_risk_level(confidence, prediction)

    # track which fields were missing and got imputed
    imputed_fields = [
        col for col in _FEATURE_COLUMNS
        if str(raw_values.get(col, '')).strip() in ('', 'None', 'none')
        and col != 'bp'
    ]

    return {
        'prediction':          'CKD' if prediction == 1 else 'Not CKD',
        'prediction_code':     prediction,
        'confidence':          round(confidence * 100, 2),
        'ckd_probability':     round(float(probabilities[1]) * 100, 2),
        'not_ckd_probability': round(float(probabilities[0]) * 100, 2),
        'risk_level':          risk_level,
        'suggested_action':    suggested_action,
        'imputed_fields':      imputed_fields,
    }, None