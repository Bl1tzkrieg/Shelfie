# Shelfie 📚

**Shelfie** es un sistema backend de código abierto diseñado para la gestión integrada de bibliotecas modernas. Utilizando un enfoque arquitectónico modular y escalable, este sistema provee herramientas completas para administrar catálogos bibliográficos, flujos transaccionales de circulación y portales de consulta pública para usuarios finales.

## 🚀 Módulos Core del Sistema

La lógica de negocio está segregada de forma modular para garantizar un mantenimiento eficiente e independiente de cada flujo bibliotecario técnico:

* **Catalogación:** Registro estructurado de ítems bibliográficos, listo para futuras integraciones con formatos estándar como MARC 21 y protocolos de comunicación Z39.50].
* **Circulación:** API encargada de procesar préstamos, gestionar devoluciones automáticas, administrar reservas físicas y calcular penalizaciones o bloqueos].
* **Gestión de Usuarios (Socios):** Registro detallado de lectores, perfiles de personal administrativo y control de acceso (Autenticación diferenciada para Intranet y OPAC)].
* **Adquisiciones y Publicaciones Seriadas:** Monitoreo de compras de material bibliográfico a proveedores externos y seguimiento a las suscripciones de revistas o diarios].
* **Informes:** Consultas de base de datos optimizadas para generar estadísticas de uso de la biblioteca, reportes de morosidad y auditorías de inventario].
* **OPAC (Online Public Access Catalog):** Servicio de endpoints públicos diseñados para búsquedas bibliográficas rápidas (básicas y avanzadas) por parte de la comunidad].


## 🔧 Instalación y Despliegue Local

1. Clona este repositorio:
   ```bash
   git clone [https://github.com/TU_USUARIO/Shelfie.git](https://github.com/TU_USUARIO/Shelfie.git)
   cd Shelfie