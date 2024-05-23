import httpx

url = ''
with httpx.stream('POST', url) as r:
    for chunk in r.iter_raw():  # or, for line in r.iter_lines():
        print(chunk)