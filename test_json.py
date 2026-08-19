import json

try:
    json.loads('{"a": "line1\nline2"}')
except Exception as e:
    print("Newline Error:", type(e), e)

try:
    json.loads('{"a": "line1')
except Exception as e:
    print("Truncation Error:", type(e), e)
