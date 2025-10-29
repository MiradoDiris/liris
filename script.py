from utils.dgraph_connector import LirisDgraphConnector

# Initialise le connecteur
connector = LirisDgraphConnector()

# Étape 1 — Récupérer toutes les relations existantes
relations_query = """
{
  relations(func: type(Relation)) {
    uid
    relationType
    source { uid }
    target { uid }
  }
}
"""
relations_data = connector.query(relations_query)

relations = relations_data.get("relations", [])
print(f"Relations trouvées : {len(relations)}")

# Étape 2 — Réinjection des relations pour forcer le recalcul des inverses
mutations = []
for rel in relations:
    src = rel.get("source", {})
    tgt = rel.get("target", {})
    if src and tgt:
        mutations.append({
            "uid": rel["uid"],
            "source": {"uid": src["uid"]},
            "target": {"uid": tgt["uid"]},
        })

if mutations:
    connector.insert_mutations(mutations)
    print(f"{len(mutations)} relations réinjectées pour recalcul des inverses.")
else:
    print("Aucune relation valide à réinjecter.")
