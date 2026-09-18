# PENDIENTES.md — Deuda técnica y elementos congelados

> Registro de decisiones, rutas muertas y trabajo diferido durante la migración
> a microservicios (FASE 1: inventario / FASE 4: retiro del monolito).
> Este archivo es la memoria del proyecto; NADA aquí se corrige sin autorización
> explícita del usuario.

---

## 1. Rutas muertas (se conservan tal cual, sin corregir su lógica)

Documentadas durante el inventario (FASE 1). Ninguna impide el arranque de los
servicios y ninguna pierde protección de acceso: como no existen como rutas en el
código, el acceso a ellas da 404 exactamente igual que en el monolito.

| Enlace (template) | URL | Por qué está muerta | Acción |
|---|---|---|---|
| `alertas.html:11`, `productos.html:66` | `/alertas/programar` | El botón "Programar reabastecimiento" apunta a una ruta que nunca tuvo `@app.route` en el monolito (404 desde siempre). | Conservar tal cual. No crear la ruta. |
| `inventario.html:88` | `/reportes/inventario` | Solo existe el exportador `/reportes/inventario/exportar`; la vista sin `/exportar` jamás se definió (404 desde siempre). | Conservar tal cual. No crear la ruta. |
| `pago.html` (plantilla huérfana) | — | Ningún `render_template('pago.html')` en el monolito; el flujo de pago real usa el modal de `carrito.html`. Nunca se renderiza. | Copiada a `tienda_service/templates/` (FASE 2). Sin lógica nueva. |

## 2. URLs fijas eliminadas (decisión FASE 2)

- Se eliminaron los `127.0.0.1:500X` hardcodeados de las plantillas.
- Ahora los enlaces/acciones entre servicios usan `{{ AUTH_SERVICE_URL }}` /
  `{{ TIENDA_SERVICE_URL }}` inyectados por context processor de cada servicio,
  alimentados desde `.env` (`AUTH_SERVICE_URL`, `TIENDA_SERVICE_URL`).
- Enlaces dentro del MISMO servicio quedan relativos (p.ej. `/clientes` en
  auth) para que el monolito y los servicios compartan la misma marca.

## 3. Compartición de plantillas/estáticos (FASE 2)

- `base.html` y `static/` son únicos (raíz del repo) y se leen desde todos los
  servicios vía `ChoiceLoader` + `static_folder` apuntando a la raíz.
- No hay copias de `base.html` ni `static/` en los servicios → no se pueden
  desincronizar.
- Estructura por servicio: `<servicio>/templates/*.html` (propias) + raíz
  `templates/` (compartidas).

## 4. Pendiente por FASE (por autorización)

- **FASE 3**: rutas no portadas aún a los servicios (inventario de rutas 1-2 en
  `AGENTS.md` / reporte FASE 1): quedan en el monolito hasta aprobación.
- **FASE 4**: retirar definitivamente `app.py` (monolito) y su `templates/`
  raíz/`static` (ya compartidas con servicios, por lo que el retiro es directo).
- **Post-migración**: revisar `seed_data.py` para no depender de credenciales
  conocidas en producción; revisar rate-limit en memoria (perderlo al reiniciar
  cada servicio) y pasar a Redis si se requiere persistencia.
