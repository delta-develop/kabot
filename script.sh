#!/bin/bash

src_dir="app"
dst_dir="tests"

# Elimina y recrea la carpeta de tests para evitar conflictos previos
rm -rf "$dst_dir"
mkdir -p "$dst_dir"

# Recorre todos los archivos en app/
find "$src_dir" -type f -name "*.py" | while read -r file; do
  # Calcula el path relativo sin el prefijo app/
  rel_path="${file#$src_dir/}"

  # Extrae el directorio destino y nombre del archivo
  dest_dir="$dst_dir/$(dirname "$rel_path")"
  filename="$(basename "$rel_path")"
  test_filename="test_$filename"

  # Crea el directorio en tests/
  mkdir -p "$dest_dir"

  # Crea un archivo de test vacío con prefijo test_
  touch "$dest_dir/$test_filename"
done

echo "Estructura de tests replicada en '$dst_dir/' con archivos test_*.py"