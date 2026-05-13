#ckdprediction/services.py
#Complete ML prediction service for CKD

import json
import pickle
import numpy as np
import os
from django.conf import settings

# ============================================================================
# LOAD ALL MODEL FILES ONCE AT STARTUP — NOT ON EVERY REQUEST
# ============================================================================

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = BASE_DIR

# Load model
try:
    with open(os.path.join(MODELS_DIR, 'ckd_model_final.pkl'), 'rb') as f:
        _MODEL = pickle.load(f)
except FileNotFoundError:
    raise Exception(f"CKD model file not found at {os.path.join(MODELS_DIR, 'ckd_model_final.pkl')}")

# Load scaler
try:
    with open(os.path.join(MODELS_DIR, 'ckd_scaler.pkl'), 'rb') as f:
        _SCALER = pickle.load(f)
except FileNotFoundError:
    raise Exception(f"CKD scaler file not found at {os.path.join(MODELS_DIR, 'ckd_scaler.pkl')}")

# Load imputation values
try:
    with open(os.path.join(MODELS_DIR, 'ckd_imputation_values.json')) as f:
        _IMPUTATION = json.load(f)
except FileNotFoundError:
    raise Exception(f"Imputation values file not found at {os.path.join(MODELS_DIR, 'ckd_imputation_values.json')}")

# Load encoding maps
try:
    with open(os.path.join(MODELS_DIR, 'ckd_encoding_maps.json')) as f:
        _ENCODING = json.load(f)
except FileNotFoundError:
    raise Exception(f"Encoding maps file not found at {os.path.join(MODELS_DIR, 'ckd_encoding_maps.json')}")

# Load feature columns
try:
    with open(os.path.join(MODELS_DIR, 'ckd_feature_columns.json')) as f:
        _FEATURE_COLUMNS = json.load(f)
except FileNotFoundError:
    raise Exception(f"Feature columns file not found at {os.path.join(MODELS_DIR, 'ckd_feature_columns.json')}")

# Derive categorical and numerical columns
_CATEGORICAL_COLS = list(_ENCODING.keys())
_NUMERICAL_COLS = [col for col in _FEATURE_COLUMNS if col not in _CATEGORICAL_COLS]

print(f"✓ CKD ML Models loaded successfully")
print(f"  - Model: {_MODEL}")
print(f"  - Features: {len(_FEATURE_COLUMNS)}")
print(f"  - Categorical: {len(_CATEGORICAL_COLS)}")
print(f"  - Numerical: {len(_NUMERICAL_COLS)}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _parse_bp(bp_value):
    """
    Parse blood pressure string.
    Nurse stores BP as "120/80" — UCI dataset uses diastolic (second number).
    
    Input: "120/80" or "80" or None
    Output: float (diastolic) or None
    """
    if not bp_value:
        return None
    
    try:
        bp_str = str(bp_value).strip()
        
        # Handle "120/80" format
        if '/' in bp_str:
            parts = bp_str.split('/')
            if len(parts) == 2:
                return float(parts[1])  # diastolic
        
        # Handle "80" format
        return float(bp_str)
    except (ValueError, IndexError, AttributeError):
        return None


def _get_risk_level(confidence, prediction):
    """
    Map prediction + confidence to clinical risk label and suggested action.
    
    Returns: (risk_level, suggested_action)
    """
    if prediction == 1:  # CKD detected
        if confidence >= 0.85:
            return (
                'High',
                'Immediate nephrology referral recommended. Begin CKD management protocol.'
            )
        elif confidence >= 0.65:
            return (
                'Moderate',
                'Further diagnostic tests recommended. Schedule follow-up within 2 weeks.'
            )
        else:
            return (
                'Low-Moderate',
                'Borderline result. Repeat KFT in 4 weeks and monitor symptoms.'
            )
    else:  # No CKD
        if confidence >= 0.85:
            return (
                'Low',
                'No indicators of CKD detected. Routine follow-up as scheduled.'
            )
        else:
            return (
                'Low-Moderate',
                'Result is negative but confidence is low. Repeat KFT in 4 weeks.'
            )


def _encode_categorical(col, raw_value):
    """
    Encode a categorical feature using the training encoding map.
    """
    raw = str(raw_value or '').strip().lower()
    mapping = _ENCODING.get(col, {})
    
    # If value matches a key in the mapping, use it
    if raw in mapping:
        return mapping[raw]
    
    # Otherwise, use the imputation default
    default_raw = str(_IMPUTATION.get(col, '')).strip().lower()
    return mapping.get(default_raw, 0)


# ============================================================================
# MAIN PREDICTION SERVICE
# ============================================================================

def service_predict_ckd(raw_values: dict, bp_string: str = None):
    """
    Predicts CKD risk based on KFT lab values and optional blood pressure.
    
    Args:
        raw_values (dict): Custom field values from the KFT record
                          Example: {"age": 55, "bp": 80, "hemo": 12.6, "htn": "no", ...}
        bp_string (str): Blood pressure string from nurse vitals
                        Example: "120/80" or None
    
    Returns:
        Tuple: (result_dict, error_string)
        - result_dict: Contains prediction, confidence, risk_level, etc.
        - error_string: Error message if prediction failed, else None
    
    Example:
        result, error = service_predict_ckd(
            raw_values={'age': 45, 'sc': 1.8, 'htn': 'yes', ...},
            bp_string='120/80'
        )
        if error:
            print(f"Error: {error}")
        else:
            print(f"CKD Risk: {result['risk_level']}")
    """
    
    try:
        features = {}
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 1: Initialize all features with imputation defaults
        # ─────────────────────────────────────────────────────────────────
        for col in _FEATURE_COLUMNS:
            features[col] = _IMPUTATION.get(col)
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 2: Override with actual values from the KFT report
        # ─────────────────────────────────────────────────────────────────
        for col in _FEATURE_COLUMNS:
            val = raw_values.get(col)
            if val is not None and str(val).strip() not in ('', 'None', 'none'):
                features[col] = val
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 3: Parse blood pressure from nurse vitals
        # ─────────────────────────────────────────────────────────────────
        parsed_bp = _parse_bp(bp_string)
        if parsed_bp is not None:
            features['bp'] = parsed_bp
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 4: Encode categorical features using training encoding maps
        # ─────────────────────────────────────────────────────────────────
        for col in _CATEGORICAL_COLS:
            features[col] = _encode_categorical(col, features.get(col))
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 5: Convert numerical features to float
        # ─────────────────────────────────────────────────────────────────
        for col in _NUMERICAL_COLS:
            try:
                val = features.get(col)
                features[col] = float(val) if val is not None else float(_IMPUTATION.get(col, 0))
            except (TypeError, ValueError):
                features[col] = float(_IMPUTATION.get(col, 0))
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 6: Build feature vector in exact training column order
        # ─────────────────────────────────────────────────────────────────
        try:
            feature_vector = np.array([
                [features[col] for col in _FEATURE_COLUMNS]
            ])
        except KeyError as e:
            return None, f"Missing critical feature: {e}"
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 7: Scale using the scaler fitted during training
        # ─────────────────────────────────────────────────────────────────
        feature_vector_scaled = _SCALER.transform(feature_vector)
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 8: Make prediction
        # ─────────────────────────────────────────────────────────────────
        prediction = int(_MODEL.predict(feature_vector_scaled)[0])
        probabilities = _MODEL.predict_proba(feature_vector_scaled)[0]
        confidence = float(probabilities[prediction])
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 9: Generate risk level and suggested action
        # ─────────────────────────────────────────────────────────────────
        risk_level, suggested_action = _get_risk_level(confidence, prediction)
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 10: Track which fields were imputed
        # ─────────────────────────────────────────────────────────────────
        imputed_fields = [
            col for col in _FEATURE_COLUMNS
            if str(raw_values.get(col, '')).strip() in ('', 'None', 'none')
            and col != 'bp'
        ]
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 11: Return structured result
        # ─────────────────────────────────────────────────────────────────
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
    
    except Exception as e:
        import traceback
        error_msg = f"Prediction error: {str(e)}"
        traceback.print_exc()
        return None, error_msg