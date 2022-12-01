def fget(path, ty=str, strip=True):
    try:
        with open(path, 'r') as f:
            res = f.read()
            if strip:
                res = res.strip()
            return ty(res)
    except FileNotFoundError:
        return None

def fset(path, value):
    if isinstance(value, bool):
        value = int(value)
    value = str(value)

    with open(path, 'w') as f:
        f.write(value)
