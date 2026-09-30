# data/raw: real source extracts

One folder per pack (`IN`, `IN-MH`, `BR`, `BR-AL`, `RU`, `RU-TY`, `CN`, `CN-NX`, `ZA`, `ZA-EC`), with one CSV per
metric named in that pack's `data/packs/<PACK>.json`. For example `data/raw/IN-MH/mpi_headcount.csv`:

```csv
district_name,value,year,source,licence,unit
Nandurbar,30.2,2019-21,"NITI Aayog National MPI Progress Review 2023, Table A-x",Public report,percent
Pune,0.05,2019-21,"NITI Aayog National MPI Progress Review 2023, Table A-x",Public report,
```

- `district_name` may be any name listed for the unit in `data/reference/<PACK>/units.csv` (English, local script,
  or an alias such as Ahilyanagar / Dharashiv), or use an `admin_code` column instead.
- `value` must be a 0-1 fraction, or a percentage with `unit=percent`.
- Cite the exact table or page in `source`. It flows row by row into `data/processed/<PACK>/indicators_long.csv`.

Optional `planned_projects.csv` in the same folder (hand-built from budget documents):

```csv
project_id,admin_code,sector,name,budget_m,currency,status,source,synthetic
MH-2026-001,IN-MH-NANDURBAR,water,Jal Jeevan multi-village scheme,125,INR,delayed,"Maharashtra budget 2026-27, Vol. X p. Y",false
```

`status`: `funded` / `sanctioned` / `in_progress` / `completed` count as funded; `delayed` / `stalled` as delayed.

After adding or changing files, from `backend/`:

```
python -m scripts.build_indicators --pack IN-MH --allow-placeholder
```

The build reports which metrics are still placeholders. Drop `--allow-placeholder` to make any gap an error.
