"""
Divide product 36 of the Spanish table into accommodation and food service.

  36  Servicios de alojamiento y de comidas y bebidas  (CPA 55-56)
        ->  36A  Servicios de alojamiento               (CNAE 55)
        ->  36B  Servicios de comidas y bebidas         (CNAE 56)

WHAT MAKES THIS DIFFERENT FROM `uk_hospitality.py`
--------------------------------------------------
Every weight in the UK example is illustrative. The output split here is not
even a proxy: the INE's supply table is **published at 110 products**, where
`73. Servicios de alojamiento` and `74. Servicios de comidas y bebidas` are
separate and sum to product 36 to the last decimal. The split is a lookup.

THAT IS A CORRECTION, AND IT COST 9.8 POINTS
---------------------------------------------
This example drove the split with the business survey's production figure until
the supply table was found. The survey gives accommodation 33.73 % of output;
the true figure is **23.95 %**. Worse, the survey key with the best conceptual
match — production against output — was the third worst of the seven available,
and employment, the loosest match, was the best at 21.24 %. The mismatch is of
population, not concept: an accommodation ENTERPRISE makes a lot of food-service
PRODUCT, and the product classification puts that in 74.

The survey keys are kept below as corroboration. They are what an analyst would
have had if the supply table did not exist, and the gap between them and the
truth is the most useful number this example contains.

That is not luck. The INE's Tabla 8 states that product 36 is CPA 55-56, so the
split is between two complete NACE divisions rather than inside one. Divisions
are what statistical offices publish. The UK pilot tried to split *within*
division 56, where purchasing patterns are not published and CORE_013 ¶B12.14
says they cannot be established from company accounts at all.

WHAT THE READER MUST NOT TAKE FROM IT
-------------------------------------
Three things, all in the assumption ledger and all in the report:

1. The table is **product by product**; the survey is **industry by industry**.
   Product 36 is every euro of accommodation and food-service output, whoever
   produced it — a factory canteen, a hotel's restaurant. The survey counts
   enterprises classified to CNAE 55 and 56. The two are not the same
   population, and the split assumes the difference falls on 55 and 56 in the
   same proportion as the part the survey does see. It covers 72 % of the
   product's output.

2. The keys disagree with each other, by a lot. Accommodation is 21 % of the
   parent by employment and 55 % by gross operating surplus. Both are correct
   measurements of different things. Any single number for "the size of
   accommodation" is a choice among them, and the corroboration table in the
   report prints the whole range rather than hiding it.

3. Two value-added rows carry their own measurement and one absorbs the rest.
   Until v1.8 the whole block took one ratio, which misplaced about 6,441
   million EUR of gross operating surplus (OQ-B-12). Imported inputs and
   compensation are now exact; **gross operating surplus is a residual** and
   must be read as an outcome of the others, not as evidence.

Run:
    python3 examples/es_hosteleria.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quadrium.disaggregation import neutralise_profile  # noqa: E402
from quadrium.io_loader import load_ine_tio  # noqa: E402
from quadrium.models import (AllocationKey, Assumption,  # noqa: E402
                              AssumptionLedger, ProfileProvenance,
                              ProxyStrength, Scenario, SplitSpec)
from quadrium.project import IOProject  # noqa: E402

TABLE = ROOT / "data" / "ine" / "cne_tio_22.xlsx"
NEW = ["36A", "36B"]
LBL = ["Servicios de alojamiento (CNAE 55)",
       "Servicios de comidas y bebidas (CNAE 56)"]

_EEE = "INE, Estadística Estructural de Empresas: Sector Servicios"
_T76815 = f"{_EEE}, tabla 76815 (resultados de explotación)"
_T76811 = f"{_EEE}, tabla 76811 (principales magnitudes)"


def build_keys() -> dict:
    """Nine keys. Two drive the split; the rest are evidence against it.

    A key registered here that no split names becomes an automatic external
    check — the report compares the split it produced against what that key
    measures and prints the gap. With one source measuring the same two
    subsectors seven different ways, that check is the honest error bar.

    All values in thousands of euros except employment (persons) and hours.
    """
    def k(key_id, block, v55, v56, source, strength=ProxyStrength.MEDIUM):
        return AllocationKey(key_id=key_id, applies_to=block,
                             new_sector_codes=NEW, raw_values=[v55, v56],
                             source=source, source_year=2022, strength=strength)

    keys = [
        # ---- driving the split ------------------------------------------
        # THE OBSERVED SPLIT. Not a proxy: the INE's own supply table, published
        # at 110 products, separates `73. Servicios de alojamiento` (CPA 55)
        # from `74. Servicios de comidas y bebidas` (CPA 56). Their outputs sum
        # to 128,266.5 — the output of product 36 in the 64-product IOT, to the
        # last decimal — so this is the same quantity, disaggregated, by the
        # office. Millions of EUR here, not thousands like the survey keys.
        k("k_tod_produccion", "output", 30_717.7, 97_548.8,
          "INE, Tablas de Origen y Destino 2022, Tabla 1 (origen a precios "
          "básicos), productos 73 y 74", ProxyStrength.STRONG),
        # The survey's production figure, which drove this split until the
        # supply table was found. Kept as corroboration, and it is the reason
        # this file now carries a warning: it is 9.8 points wrong. See A-07.
        k("k_produccion", "output", 31_167_086, 61_233_490,
          f"{_T76815}, `Valor de la producción`"),
        # `Valor añadido a precios de mercado` is production less intermediate
        # consumption, which is what the table's VA block is (output less
        # domestic intermediate) apart from its imports and product-tax rows.
        # Those two rows are the part this key cannot speak for — see A-04.
        k("k_vab", "value_added", 16_403_219, 24_768_118,
          f"{_T76815}, `Valor añadido a precios de mercado`",
          ProxyStrength.STRONG),

        # ---- registered as evidence, not used to drive ------------------
        k("k_empleo", "output", 342_956, 1_271_964,
          f"{_T76811}, `Personal ocupado` (personas)"),
        k("k_horas", "output", 556_585, 1_456_295,
          f"{_T76811}, `Horas trabajadas por el personal remunerado`"),
        k("k_gastos_personal", "output", 9_444_965, 19_384_933,
          f"{_T76815}, `Gastos de personal`"),
        k("k_ebe", "output", 6_634_659, 5_387_752,
          f"{_T76815}, `Excedente bruto de explotación`"),
        k("k_compras", "output", 15_863_771, 37_368_585,
          f"{_T76811}, `Total de compras de bienes y servicios`"),
        # Counting businesses is not a size proxy: a restaurant is small and
        # there are 265,125 of them. WEAK, so the engine excludes it from the
        # corroboration and reports it as skipped rather than letting a 220 %
        # "disagreement" dilute the checks that mean something.
        k("k_empresas", "output", 31_224, 265_125,
          f"{_T76811}, `Número de empresas`", ProxyStrength.WEAK),
        # Near-collinear with the driving key: turnover and production differ
        # only by inventory change and own-account work. Its agreement is
        # arithmetic, not corroboration. Registered so the report can say so.
        k("k_cifra_negocios", "output", 31_177_126, 61_241_052,
          f"{_T76815}, `Cifra de negocios`"),
    ]
    return {k_.key_id: k_ for k_ in keys}


# Relative purchasing intensities, 1.00 = the parent's average.
#
# OBSERVED, not invented. The survey splits each subsector's inputs into goods
# (`consumo de materias primas` + `consumo de bienes para reventa`) and services
# (`gastos en servicios exteriores`). A restaurant buys food; a hotel rents a
# building.
#
# They are applied only where the mapping from those two categories to a product
# of the table is not in doubt. Everything else keeps the parent's average,
# which is the honest treatment of a supplier the evidence cannot place. `5`
# (food, drink, tobacco) is the parent's largest supplier at 37.0 % of its
# inputs and `44` (real estate) the second at 11.8 %, so the two categories
# cover most of what moves.
_GOODS = ("1", "5")             # agriculture; food, beverages, tobacco
_SERVICES = ("44", "50", "53")  # real estate; renting; building & security svcs

# EEE 2022, thousands of EUR: (goods, services) purchased by each subsector.
_EEE_INPUTS = {
    "36A": (4_164_631 + 1_179_427, 10_599_236),
    "36B": (25_322_338 + 820_036, 11_143_034),
}


def build_profiles(table, w_col) -> dict:
    """Turn the survey's goods/services split into level-neutral intensities.

    The raw intensities are the observed part: each subsector's goods share
    divided by the parent's. Everything after that is the engine's
    `neutralise_profile()`, which is where the correction now lives — the pilot
    used to carry its own fixed point, and got it wrong the first time.

    WHY THE NEUTRALISATION IS NOT OPTIONAL HERE.
    The engine normalises intensities per SUPPLIER, which keeps each supplier's
    total sales to the group unchanged. Nothing then keeps each SUBSECTOR's
    total purchases where the allocation key put them, so a profile moves the
    level as a side effect of describing the composition. That is normally
    absorbed by the internal block. Product 36's diagonal is 154.9 — 0.12 % of
    its input column — and the raw profile below moves 915. Six times the room
    available, and the scenario is refused.

    The UK pilot never hit this: its profiles move 161 and 516 against internal
    blocks of 887 and 1,322. Same engine, same kind of profile; the difference
    is that a product-by-product table has a much thinner diagonal than an
    industry-by-industry one. Both figures now print in the report.
    """
    g_tot = sum(v[0] for v in _EEE_INPUTS.values())
    s_tot = sum(v[1] for v in _EEE_INPUTS.values())
    parent_goods = g_tot / (g_tot + s_tot)
    raw = {}
    for code, (g, s) in _EEE_INPUTS.items():
        raw[code] = {**{c: (g / (g + s)) / parent_goods for c in _GOODS},
                     **{c: (s / (g + s)) / (1.0 - parent_goods)
                        for c in _SERVICES}}
    out = neutralise_profile(table, "36", NEW, w_col, raw)
    print(f"  perfil crudo desplazaba {out['shift_before']:,.1f} M€ contra un "
          f"bloque interno de {table.Z[table.index_of('36'), table.index_of('36')]:,.1f}"
          f"; neutralizado a {out['shift_after']:.1e} en {out['iterations']} iteraciones")
    return out["profiles"]


def build_ledger() -> AssumptionLedger:
    led = AssumptionLedger(project_id="es_hosteleria")
    led.add(Assumption(
        assumption_id="A-01",
        description="The table is product by product (CPA 55-56); the survey is "
                    "industry by industry (CNAE 55, 56). Product 36 counts all "
                    "accommodation and food-service output whoever produced it, "
                    "including as a secondary product of another industry. The "
                    "survey's `valor de la producción` for hostelería is 92,401 "
                    "million EUR against the product's 128,266 million: it sees "
                    "72 %. Applying its ratio assumes the 28 % it does not see "
                    "divides between 55 and 56 the same way.",
        applies_to="every block of the split",
        source=f"{_T76815}; INE TIO 2022 Tabla 8 (correspondence CPA/NACE)",
        validated_by="scale checked against the table on load; the residual "
                     "28 % is NOT SPECIFIED as to composition",
        confidence=ProxyStrength.MEDIUM,
        impact_on_results="unquantified — it is the central assumption"))
    led.add(Assumption(
        assumption_id="A-02",
        description="The survey measures the same two subsectors seven ways and "
                    "they disagree: accommodation is 21.2 % of the parent by "
                    "persons employed, 29.8 % by purchases, 32.8 % by personnel "
                    "cost, 33.7 % by output, 39.8 % by value added and 55.2 % by "
                    "gross operating surplus. The split is driven by output and "
                    "value added; the rest are printed as corroboration. The "
                    "spread is the uncertainty, and it is not narrow.",
        applies_to="the choice of driving key",
        source=f"{_T76815}, {_T76811}",
        validated_by="corroboration table in the report",
        confidence=ProxyStrength.MEDIUM,
        impact_on_results="large — a different key moves output by up to 21 "
                          "points of the parent"))
    led.add(Assumption(
        assumption_id="A-03",
        description="Input profiles come from the survey's own goods/services "
                    "split of each subsector's purchases, not from judgement. "
                    "They are applied only to suppliers whose mapping to one of "
                    "those two categories is unambiguous (products 1 and 5 for "
                    "goods; 44, 50 and 53 for premises-type services). Every "
                    "other supplier keeps the parent's average intensity.",
        applies_to="scenario S2_perfilado",
        source=f"{_T76815}, `consumo de materias primas`, `consumo de bienes "
               f"para reventa`, `gastos en servicios exteriores`",
        validated_by="supplier totals preserved by construction; reaggregation "
                     "checked",
        confidence=ProxyStrength.MEDIUM,
        impact_on_results="changes input structure, not subsector size"))
    led.add(Assumption(
        assumption_id="A-04",
        description="Two value-added rows are pinned to their own measurement "
                    "— imported inputs at 29.80 % and compensation at 32.76 % — "
                    "and gross operating surplus absorbs the remainder at "
                    "34.88 %. Until v1.8 the whole block took one ratio of "
                    "39.84 %, misplacing +6,441, -2,164 and -479 million EUR on "
                    "those three rows (OQ-B-12). What cannot be done is pin all "
                    "three: the survey's own GOS share of 55.19 % leaves the "
                    "subsector buying -8,470 from its sibling, worse than the "
                    "flat key. GOS here is an OUTCOME, not a measurement.",
        applies_to="the VA block of the split",
        source=f"{_T76815}, rows `Total de compras` and `Gastos de personal`",
        validated_by="each row sums back to its parent; the residual share is checked to lie in [0,1] and refused otherwise (OQ-B-12)",
        confidence=ProxyStrength.STRONG,
        impact_on_results="two of five rows now carry a measurement; the surplus row moved 1.15 points and is a residual"))
    led.add(Assumption(
        assumption_id="A-05",
        description="The table it splits carries a RESIDUAL final-demand column "
                    "of 4,921.6 million EUR on agricultural products, computed "
                    "by the loader because the INE's interior table does not "
                    "balance there (OQ-D-04). Product 36 is not the affected "
                    "product, but the residual is inside the table this result "
                    "is built on.",
        applies_to="the loaded table",
        source="INE TIO 2022, Tabla 2; see data/ine/README.md",
        validated_by="isolated to one product on load",
        confidence=ProxyStrength.STRONG,
        impact_on_results="none on product 36 directly"))
    led.add(Assumption(
        assumption_id="A-07",
        description="The output split is OBSERVED, not estimated. The INE's "
                    "supply table is published at 110 products, where CPA 55 "
                    "and CPA 56 are separate and sum to product 36 exactly. "
                    "This corrects the pilot: it previously used the business "
                    "survey's production figure, which gives accommodation "
                    "33.73 % against a true 23.95 % — 9.8 points wrong, and the "
                    "survey key with the BEST conceptual match to output was "
                    "among the worst. Employment, the loosest match, was the "
                    "closest at 21.24 %. The reason is population, not concept: "
                    "an accommodation ENTERPRISE produces a great deal of "
                    "food-service PRODUCT, and the product classification "
                    "assigns that to 74.",
        applies_to="the output block, and through it every other",
        source="INE, Tablas de Origen y Destino 2022, Tabla 1, products 73/74",
        validated_by="sums to the IOT's product 36 output to 0.0000",
        confidence=ProxyStrength.STRONG,
        impact_on_results="corrects a 9.8 point error in the driving key"))
    led.add(Assumption(
        assumption_id="A-06",
        description="The survey's value-added evidence CANNOT be used, and S3 "
                    "records the refusal. Product 36's column has value added "
                    "at 61.3 % of output; the surveyed hospitality industry has "
                    "44.6 %. The gap is the 28 % of the product the survey does "
                    "not see, and it is far more value-added intensive than the "
                    "part it does. Inside so high a parent ratio, giving "
                    "accommodation 39.84 % of value added on 33.73 % of output "
                    "leaves it buying -4,755 million EUR from its sibling. The "
                    "ceiling is 33.80 % with inherited purchases and 36.27 % "
                    "with the survey's own purchases key; the observed 39.84 % "
                    "clears neither. S1 and S2 therefore split value added in "
                    "proportion to output — not because that is right, but "
                    "because the only other evidence available does not fit the "
                    "accounts.",
        applies_to="scenarios S1_proporcional and S2_perfilado",
        source=f"{_T76815}; feasibility ceiling derived from the parent column",
        validated_by="the engine refuses S3 and the report carries the reason",
        confidence=ProxyStrength.STRONG,
        impact_on_results="the value-added split is an assumption, not a "
                          "measurement, and no corroboration key rescues it"))
    return led


def main() -> int:
    table = load_ine_tio(TABLE, variant="interior", unbalanced="residual_column")
    j = table.index_of("36")
    print(f"Cargada {table.table_id}: {table.n} productos, {table.unit}")
    print(f"  36 {table.sector_labels[j][:52]:<54} "
          f"producción {table.X[j]:>10,.1f}")
    print(f"     consumos intermedios interiores (columna) "
          f"{table.Z[:, j].sum():>10,.1f}")
    print(f"     bloque de valor añadido (columna)         "
          f"{table.VA[:, j].sum():>10,.1f}")
    print(f"     diagonal propia Z[36,36]                  "
          f"{table.Z[j, j]:>10,.1f}")

    # Only `output` is fixed on the split, so each scenario is free to say
    # something different about the value-added block. That is the whole point
    # of S3.
    keys = build_keys()
    w_out = keys["k_tod_produccion"].w
    profiles = build_profiles(table, w_out)
    print("  perfiles de compra observados (1.00 = media del padre):")
    for code, prof in profiles.items():
        g, s = prof[_GOODS[0]], prof[_SERVICES[0]]
        print(f"    {code}: bienes x{g:.3f}   servicios x{s:.3f}")

    # Two value-added rows carry their own measurement. The survey gives
    # accommodation 29.80 % of purchases and 32.76 % of personnel cost against
    # a block key of 33.73 %; the block total still follows that key and gross
    # operating surplus — the residual item in the accounts — absorbs the
    # difference. OQ-B-12. Before this existed the block took one ratio and
    # misplaced 6,441 million EUR of operating surplus.
    va_rows = {table.VA_labels[0]: "k_compras",
               table.VA_labels[2]: "k_gastos_personal"}
    splits = [SplitSpec("36", NEW, LBL,
                        keys_by_block={"output": "k_tod_produccion"},
                        va_row_keys=va_rows,
                        va_residual_row=table.VA_labels[4])]
    project = IOProject(
        project_id="es_hosteleria", table=table, splits=splits,
        scenarios=[
            Scenario(scenario_id="S1_proporcional", label="Sólo tamaño",
                     description="Un único dato observado: la producción. Todo "
                                 "lo demás hereda esa proporción, incluido el "
                                 "valor añadido. Es la línea de base contra la "
                                 "que se miden las otras dos."),
            Scenario(scenario_id="S2_perfilado",
                     label="Estructuras de compra observadas",
                     description="Mismo tamaño, más los perfiles de compra de "
                                 "la EEE: la restauración compra alimentos, el "
                                 "alojamiento alquila inmuebles. Cambia la "
                                 "estructura de inputs, no el tamaño.",
                     input_profiles=profiles,
                     profile_provenance=ProfileProvenance(
                         source=f"{_T76815}, `consumo de materias primas` + "
                                f"`consumo de bienes para reventa` frente a "
                                f"`gastos en servicios exteriores`",
                         source_year=2022,
                         strength=ProxyStrength.MEDIUM,
                         notes="Aplicado sólo a los proveedores cuya "
                               "correspondencia con una de las dos categorías "
                               "no admite duda; el resto conserva la "
                               "intensidad media del padre.")),
            # Expected to be INFEASIBLE, and that is the finding. Kept in the
            # run so the report carries the explanation instead of the failure
            # living only in someone's memory.
            Scenario(scenario_id="S3_va_observado",
                     label="Valor añadido observado (inviable)",
                     description="Añade las dos claves observadas que faltan: "
                                 "el valor añadido y las compras de la EEE. La "
                                 "encuesta dice que el alojamiento tiene el "
                                 "39,8 % del valor añadido con el 33,7 % de la "
                                 "producción. Esa combinación no cabe en la "
                                 "columna del producto 36 y el motor la "
                                 "rechaza. Véase A-06.",
                     keys_by_block={"value_added": "k_vab",
                                    "intermediate_cols": "k_compras"},
                     input_profiles=profiles),
        ],
        keys=keys, ledger=build_ledger(),
        title="Hostelería española — alojamiento frente a comidas y bebidas",
        source_file=TABLE, root=ROOT / "outputs",
        preamble="> **Los pesos son datos observados**, de la Estadística "
                 "Estructural de Empresas del INE para el mismo año que la "
                 "tabla. Lo que no es observado es que una encuesta de "
                 "*industrias* pueda repartir un *producto*: véase A-01, y la "
                 "tabla de corroboración antes de citar cualquier cifra.")
    project.run().write()

    print()
    for res in project.results:
        b, r = res.diagnostics["balance_info"], res.report
        print(f"  {res.scenario_id:<14s} {b['method']:<5s} "
              f"conv={b['converged']} iters={b['iterations_per_split']} "
              f"reagg={r.reaggregation_error_pct:.1e} % "
              f"signchg={b['sign_changes']} "
              f"-> {'PASA' if r.passed else 'FALLA'} ({r.n_warnings} avisos)")
    res = project.results[0]
    a, b_ = res.table.index_of("36A"), res.table.index_of("36B")
    print(f"\n  36A producción {res.table.X[a]:>10,.1f}  "
          f"({res.table.X[a] / table.X[j]:.1%} del padre)")
    print(f"  36B producción {res.table.X[b_]:>10,.1f}  "
          f"({res.table.X[b_] / table.X[j]:.1%} del padre)")
    print(f"\nCarpeta del proyecto: {project.dir}")
    return 0 if all(r.report.passed for r in project.results) else 1


if __name__ == "__main__":
    sys.exit(main())
