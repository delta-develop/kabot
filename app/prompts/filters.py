FILTER_EXTRACTION_PROMPT = """
	Actúa como un experto en búsqueda en OpenSearch. A partir de una consulta del usuario, construye un objeto JSON que represente una búsqueda híbrida con el siguiente esquema:

	- Usa `match` para campos de texto como `make`, `model`, `version`.
	- Usa `term` para campos booleanos como `bluetooth`, `car_play`.
	- Usa `range` para condiciones numéricas como `price`, `km`, `year`, etc.
	- Los filtros deben aplicarse sobre campos que viven en `metadata`, por ejemplo: `"metadata.make"`, `"metadata.price"`, etc.
	- No incluyas el vector. Solo genera el cuerpo del `bool` para combinarse luego con una búsqueda KNN.

	Ejemplo:

	Usuario pregunta: "mazda con car play y menos de 400 mil"

	Respuesta:
	{{
		"should": [ {{ "match": {{ "metadata.make": "Mazda" }} }} ],
		"filter": [
			{{ "term": {{ "metadata.car_play": true }} }},
			{{ "range": {{ "metadata.price": {{ "lte": 400000 }} }} }}
		],
		"minimum_should_match": 1
	}}

	Consulta del usuario:
	"{query}"

	Responde solo con el objeto JSON, sin explicaciones ni formato Markdown.
	"""
