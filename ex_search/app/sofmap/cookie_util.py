def create_cookies(is_akiba: bool, is_ucaa: bool):
    results = []
    if is_akiba and is_ucaa:
        cookie_data = {
            "name": "UCAA",
            "value": "on",
            "domain": "a.sofmap.com",
            "path": "/",
        }
        results.append(cookie_data)
    return results
