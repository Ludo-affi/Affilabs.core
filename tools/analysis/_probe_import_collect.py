import traceback, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    import collect_training_data as m
    print('Imported collect_training_data OK')
    print('Module file:', getattr(m, '__file__', None))
    print('Has OptimalProcessor:', hasattr(m, 'OptimalProcessor'))
    print('Dir filter Opt*:', [k for k in dir(m) if k.lower().startswith('opt')])
except Exception:
    traceback.print_exc()
