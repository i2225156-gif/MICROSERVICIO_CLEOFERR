with open('tienda_service\\app.py', 'r') as f:
    content = f.read()

# Replace the beginning section - exact match
old = "import os\nimport sys\nfrom flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, g\nfrom flask_bcrypt import Bcrypt\nfrom functools import wraps\nfrom werkzeug.utils import secure_filename\nfrom dotenv import load_dotenv\nimport jwt\n\nload_dotenv()\n\n# Si hay token, verificarlo\nif \"usuario_id\" not in session:\n    pass"

new = "import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n\nimport os\nimport sys\nfrom flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, g, make_response\nfrom flask_bcrypt import Bcrypt\nfrom functools import wraps\nfrom werkzeug.utils import secure_filename\nfrom dotenv import load_dotenv\nimport jwt as pyjwt\n\nload_dotenv()\n\n# Si hay token, verificarlo\nif \"usuario_id\" not in session:\n    pass"

if old in content:
    content = content.replace(old, new)
    print('Replaced tienda_service app.py beginning')
else:
    print('Old string not found')
    print('First 300 chars:', repr(content[:300]))

with open('tienda_service\\app.py', 'w') as f:
    f.write(content)

print('Done')