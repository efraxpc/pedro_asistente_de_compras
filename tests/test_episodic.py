from compraslab.memory import guardar_episodio, nueva_sesion, recuperar_episodios


def test_recuerdos_vectoriales_aislados_y_historicos(tmp_path):
    ruta = tmp_path / "memoria.sqlite3"
    anterior = nueva_sesion(ruta, "u1", "dataset-viejo")
    actual = nueva_sesion(ruta, "u1", "dataset-nuevo")
    otro = nueva_sesion(ruta, "u2", "dataset-nuevo")
    guardar_episodio(ruta, "u1", anterior, "dataset-viejo", "compré monitores",)
    guardar_episodio(ruta, "u1", actual, "dataset-nuevo", "consulté teclados")
    guardar_episodio(ruta, "u2", otro, "dataset-nuevo", "compré monitores")
    hallados = recuperar_episodios(ruta, "u1", "monitores", k=2)
    assert hallados[0]["dataset_id"] == "dataset-viejo"
    assert len(hallados) == 2
    assert all(r["session_id"] != otro for r in hallados)
