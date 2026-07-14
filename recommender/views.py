import json
from django.shortcuts import render, redirect
from .data_loader import load_rules, load_crop_dataset, load_fertilizer_dataset
from .engine import (
    PARAM_CONFIG, PARAM_MAP, get_soil_status, parse_rdf_ratio, adjust_npk,
    convert_to_fertilizer, estimate_yield, match_rule_for_param
)

rules = load_rules()
crop_data = load_crop_dataset()
fert_data = load_fertilizer_dataset()

def get_states():
    all_states = set(s for s in crop_data.keys() if crop_data[s])
    all_states.update(s for s in fert_data.keys() if fert_data[s])
    return sorted(all_states)

def get_crops_for_state(state):
    seen = set()
    crops = []
    for r in crop_data.get(state, []):
        name = r['crop']
        if name and name not in seen:
            seen.add(name)
            crops.append(name)
    for r in fert_data.get(state, []):
        name = r['crop']
        if name and name not in seen:
            seen.add(name)
            crops.append(name)
    return crops

def _find_record(records, name):
    nl = name.strip().lower()
    # 1. Exact match
    for rec in records:
        rc = rec['crop'].lower().strip()
        if rc == nl:
            return rec
    # 2. Base name match (strip parenthetical)
    base = nl.split('(')[0].strip()
    if base:
        for rec in records:
            rc = rec['crop'].lower().strip()
            rc_base = rc.split('(')[0].strip()
            if rc_base == base:
                return rec
    # 3. Search name contains record name (substantive substring)
    for rec in records:
        rc = rec['crop'].lower().strip()
        if len(rc) >= 5 and rc in nl:
            return rec
    return None

def home(request):
    state_crops = {}
    for state in get_states():
        state_crops[state] = get_crops_for_state(state)
    return render(request, 'recommender/home.html', {
        'states': get_states(),
        'all_crops': sorted(set(c for cs in state_crops.values() for c in cs)),
        'state_crops_json': json.dumps(state_crops, ensure_ascii=False),
    })

IDEAL_REF_VALUES = {
    'ph': 7.0, 'ec': 0.4, 'organic_carbon': 0.8,
    'nitrogen': 400, 'phosphorus': 40, 'potassium': 240,
    'sulphur': 15, 'calcium': 3.0, 'magnesium': 2.0,
    'zinc': 0.9, 'iron': 7.0, 'manganese': 3.0,
    'copper': 0.3, 'boron': 0.75,
}

def build_param_results_from_values(values_dict):
    results_list = []
    for key, _ in PARAM_CONFIG:
        value = values_dict.get(key, 0.0)
        short_status, full_status, label = get_soil_status(key, value)
        rule = match_rule_for_param(key, short_status, rules)
        practice = rule['practice'] if rule else ''
        dose = rule['dose'] if rule else ''
        results_list.append({
            'key': key,
            'label': label,
            'value': value,
            'status': short_status + (' (' + full_status.split('(')[1] if '(' in full_status else ''),
            'practice': practice,
            'dose': dose,
        })
    return results_list

def soil_test_choice(request):
    state = request.POST.get('state', '')
    crop = request.POST.get('crop', '')
    has_report = request.POST.get('has_report')
    if not state or not crop:
        return render(request, 'recommender/home.html', {
            'states': get_states(),
            'error': 'Please select a state and crop.',
        })
    if has_report == 'no':
        state_records = fert_data.get(state, [])
        found = _find_record(state_records, crop)
        urea = found['urea'] if found else 0
        dap = found['dap'] if found else 0
        mop = found['mop'] if found else 0
        return render(request, 'recommender/results.html', {
            'states': get_states(), 'state': state, 'crop': crop,
            'has_report': 'no',
            'urea': urea, 'dap': dap, 'mop': mop,
        })
    return render(request, 'recommender/soil_params.html', {
        'states': get_states(),
        'state': state,
        'crop': crop,
        'has_report': has_report,
        'params': PARAM_CONFIG,
    })

def results(request):
    state = request.POST.get('state', '')
    crop = request.POST.get('crop', '')
    has_report = request.POST.get('has_report')

    if not state or not crop:
        return render(request, 'recommender/home.html', {
            'states': get_states(),
            'error': 'Please select a state and crop.',
        })

    if has_report == 'yes':
        soil_values = {}
        for key, _ in PARAM_CONFIG:
            val = request.POST.get(key, '').strip()
            try:
                soil_values[key] = float(val) if val else 0.0
            except ValueError:
                soil_values[key] = 0.0

        param_results = build_param_results_from_values(soil_values)

        crop_records = crop_data.get(state, [])
        rdf_rec = _find_record(crop_records, crop)
        rdf_ratio = rdf_rec['rdf_ratio'] if rdf_rec else ''

        n_rdf, p_rdf, k_rdf = parse_rdf_ratio(rdf_ratio)
        n_status = get_soil_status('nitrogen', soil_values.get('nitrogen', 0))[0]
        p_status = get_soil_status('phosphorus', soil_values.get('phosphorus', 0))[0]
        k_status = get_soil_status('potassium', soil_values.get('potassium', 0))[0]

        n_adj, p_adj, k_adj = adjust_npk(n_rdf, p_rdf, k_rdf, n_status, p_status, k_status)
        urea, dap, mop = convert_to_fertilizer(n_adj, p_adj, k_adj)
        normal_yield, rec_yield = estimate_yield(n_adj, n_rdf, p_adj, p_rdf, k_adj, k_rdf)

        state_records = fert_data.get(state, [])
        default_found = _find_record(state_records, crop)
        current_urea = default_found['urea'] if default_found else 0
        current_dap = default_found['dap'] if default_found else 0
        current_mop = default_found['mop'] if default_found else 0

        return render(request, 'recommender/results.html', {
            'states': get_states(),
            'state': state,
            'crop': crop,
            'has_report': has_report,
            'param_results': param_results,
            'rdf_ratio': rdf_ratio,
            'n_rdf': n_rdf, 'p_rdf': p_rdf, 'k_rdf': k_rdf,
            'n_adj': round(n_adj, 2), 'p_adj': round(p_adj, 2), 'k_adj': round(k_adj, 2),
            'urea': urea, 'dap': dap, 'mop': mop,
            'current_urea': current_urea, 'current_dap': current_dap, 'current_mop': current_mop,
            'normal_yield': normal_yield, 'rec_yield': rec_yield,
            'chart_labels': json.dumps(['Normal Farmer Practice', 'Recommended Fertilizer']),
            'chart_data': json.dumps([normal_yield, rec_yield]),
            'fert_chart_labels': json.dumps(['Urea', 'DAP', 'MOP']),
            'fert_chart_current': json.dumps([current_urea, current_dap, current_mop]),
            'fert_chart_required': json.dumps([urea, dap, mop]),
        })

    elif has_report == 'no':
        state_records = fert_data.get(state, [])
        found = _find_record(state_records, crop)
        urea = found['urea'] if found else 0
        dap = found['dap'] if found else 0
        mop = found['mop'] if found else 0

        return render(request, 'recommender/results.html', {
            'states': get_states(),
            'state': state,
            'crop': crop,
            'has_report': has_report,
            'urea': urea,
            'dap': dap,
            'mop': mop,
        })

    return render(request, 'recommender/home.html', {
        'states': get_states(),
        'error': 'Invalid request.',
    })
