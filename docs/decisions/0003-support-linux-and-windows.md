# ADR-0003 — Soporte oficial para Linux y Windows

**Estado:** accepted  
**Fecha:** 2026-08-02  
**Decisores:** equipo Faro  
**Afecta:** instalación, rutas, descubrimiento de ejecutables, pruebas y distribución

## Contexto

Faro nació como un prototipo ejecutado en Ubuntu. El proyecto continuará como producto independiente y debe poder utilizarse tanto en Linux como en Windows, que son los sistemas más probables en pequeñas empresas.

La solución usa Python, SQLite, Poppler y Tesseract. Python y SQLite son portables, pero la instalación y localización de ejecutables externos cambia por sistema operativo.

## Decisión

Faro tendrá soporte oficial para:

- Linux de 64 bits;
- Windows 10 y Windows 11 de 64 bits.

El sistema operativo se detectará de forma centralizada. Las rutas se construirán con `pathlib` y los ejecutables externos se localizarán mediante configuración explícita o búsqueda en `PATH`.

La lógica de negocio no contendrá condiciones dispersas por sistema operativo. Las diferencias se encapsularán en módulos de plataforma y adaptadores de infraestructura.

La interfaz canónica será ejecutable mediante Python. `make` se conservará como comodidad en Linux, pero no será requisito para Windows.

## Alternativas consideradas

### Mantener soporte exclusivo para Ubuntu

Rechazada porque limita el uso potencial en empresas que operan con Windows.

### Exigir WSL en Windows

Rechazada como ruta principal porque agrega complejidad para usuarios no técnicos. Puede documentarse como alternativa de desarrollo.

### Contenerizar toda la aplicación

Pospuesta. Docker puede ser útil para desarrollo o despliegue, pero no reemplaza una experiencia local sencilla para el MVP.

## Consecuencias

Positivas:

- mayor aplicabilidad práctica;
- rutas y comandos más portables;
- errores de dependencias más claros;
- CI capaz de detectar regresiones específicas de plataforma.

Costos y riesgos:

- documentación separada por sistema;
- instalación diferente de Poppler y Tesseract;
- necesidad de pruebas en dos sistemas;
- cuidado especial con separadores, codificación y permisos.

## Plan de validación

La capacidad no se marcará como `implemented` hasta demostrar:

1. instalación desde un clon limpio en Linux;
2. instalación desde un clon limpio en Windows;
3. detección correcta del sistema operativo;
4. descubrimiento configurable de Poppler y Tesseract;
5. rutas relativas y absolutas válidas en ambos sistemas;
6. ejecución de pruebas en CI para Linux y Windows;
7. mensajes estructurados cuando falte una dependencia.

## Plan de reversión

Si una función no puede operar de forma equivalente en Windows, deberá quedar deshabilitada con un diagnóstico explícito. El núcleo de ingesta, calidad y SQLite no deberá depender del OCR para iniciar.
