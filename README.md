# KYC CLIENTES - Sistema de Verificación y Registro en la Nube con Acceso Mundial

**KYC CLIENTES** es una aplicación integral diseñada para la recepción, análisis inteligente (OCR), almacenamiento en la nube, control de frecuencia/duplicidad de documentos de identidad (Cédulas, Pasaportes, DNI) y control jerárquico de accesos con túnel público seguro para que usuarios autorizados puedan conectarse **desde su casa o desde cualquier lugar del mundo**.

---

## 🌍 Enlace de Acceso Mundial (Para Manuel, Iosef y Tú)

Gracias a la integración del conector seguro de alta velocidad (**Cloudflare Tunnel**), la aplicación cuenta con un enlace público HTTPS cifrado accesible globalmente desde cualquier teléfono celular, tablet o computadora con conexión a internet:

👉 **[https://shortly-knowledgestorm-list-ocean.trycloudflare.com/login](https://shortly-knowledgestorm-list-ocean.trycloudflare.com/login)**

*(También puedes compartir el **Código QR** que aparece dentro del sistema haciendo clic en el botón superior **"🔗 Compartir Link"** para que lo escaneen directamente con la cámara de su móvil).*

---

## 👥 Cuentas de Acceso Autorizadas

El acceso está protegido exclusivamente mediante usuario y contraseña (el auto-registro público ha sido retirado):

| # | Usuario | Contraseña | Nombre | Rol | Permisos |
|---|---|---|---|---|---|
| **1** | `admin` | `Admin2026*` | **Propietario (Tú)** | **Propietario** | **Control Total**: Subir documentos, ver frecuencias, **eliminar registros/cédulas**, **eliminar usuarios**, configurar nube |
| **2** | `mmursuli` | `Manuel2026*` | **Manuel Mursuli** | **Operador KYC** | Subir cédulas/pasaportes, ver historial y consultar frecuencias (Sin permisos de eliminación) |
| **3** | `ibavo` | `Iosef2026*` | **Iosef Bavo** | **Operador KYC** | Subir cédulas/pasaportes, ver historial y consultar frecuencias (Sin permisos de eliminación) |

---

## 🔒 Permisos Exclusivos del Propietario

- **Eliminar Registros y Cédulas**: Solo visible y permitido para `admin`. En caso de que un operador intente borrar datos, el servidor devuelve un error `403 Prohibido`.
- **Eliminar Operadores**: Solo `admin` puede remover usuarios.

---

## 🚀 Cómo Iniciar la Aplicación con Acceso Mundial

Simplemente haz doble clic en el archivo:
```bat
run.bat
```
El script iniciará el servidor web, activará el túnel seguro para todo el mundo e imprimirá en pantalla los enlaces listos para compartir con Manuel Mursuli e Iosef Bavo.
