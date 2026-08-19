import re
with open('C:/Users/PROSPERO/Aethera/python/aethera/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the ghost_resolve function
old_code = '''    resolver = GhostResolver()
    report = resolver.solve(polygons, req.global_enclosure, Scalar(req.global_area))
    resolved = {p.name: p.area.to_f64() if p.area else 0.0 for p in report.polygons}
    return GhostResolveResponse(
        resolved_areas=resolved,
        red_flags=[asdict(r) if hasattr(r, '__dataclass_fields__') else r.__dict__ for r in report.red_flags],
        rationale_log=[asdict(r) if hasattr(r, '__dataclass_fields__') else r.__dict__ for r in report.rationale_log],
        sealed_hash=report.sealed_hash,
        note="Areas derived via topological residual closure. No pre-computed areas used.",
    )'''

new_code = '''    resolver = GhostResolver()
    report = resolver.solve(polygons, req.global_enclosure, Scalar(req.global_area))
    resolved = {p.name: p.area.to_f64() if p.area else 0.0 for p in report.polygons}
    
    # Convert red_flags and rationale_log to dicts, handling Scalar serialization
    red_flags = []
    for r in report.red_flags:
        if hasattr(r, '__dataclass_fields__'):
            flag_dict = asdict(r)
            # Convert any Scalar objects to float
            for key, val in flag_dict.items():
                if hasattr(val, 'to_f64'):
                    flag_dict[key] = val.to_f64()
            red_flags.append(flag_dict)
        else:
            red_flags.append(r.__dict__ if hasattr(r, '__dict__') else str(r))
    
    rationale_log = []
    for r in report.rationale_log:
        if hasattr(r, '__dataclass_fields__'):
            log_dict = asdict(r)
            # Convert any Scalar objects to float
            for key, val in log_dict.items():
                if hasattr(val, 'to_f64'):
                    log_dict[key] = val.to_f64()
            rationale_log.append(log_dict)
        else:
            rationale_log.append(r.__dict__ if hasattr(r, '__dict__') else str(r))
    
    return GhostResolveResponse(
        resolved_areas=resolved,
        red_flags=red_flags,
        rationale_log=rationale_log,
        sealed_hash=report.sealed_hash,
        note="Areas derived via topological residual closure. No pre-computed areas used.",
    )'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('C:/Users/PROSPERO/Aethera/python/aethera/api.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed ghost_resolve endpoint')
else:
    print('Could not find exact match')
