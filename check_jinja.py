from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("tienda_service/templates"))
env.get_template("productos.html")
print("JINJA OK productos.html")
