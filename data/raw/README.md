# data/raw: real source extracts

One CSV per metric named in `data/packs/IN-MH.json`, e.g. `mpi_headcount.csv`:

```csv
district_name,value,year,source,licence,unit
Nandurbar,30.2,2019-21,"NITI Aayog National MPI Progress Review 2023, Table A-x",Public report,percent
Pune,0.05,2019-21,"NITI Aayog National MPI Progress Review 2023, Table A-x",Public report,
```

- `district_name` may be any spelling listed in `data/reference/districts_IN-MH.csv`
  (English, Marathi, or an alt name such as Ahilyanagar / Dharashiv), or use an `admin_code` column instead.
- `value` must be a 0-1 fraction, or a percentage with `unit=percent`.
- Cite the exact table or page in `source`. It flows row by row into `data/processed/indicators_long.csv`.

Optional `planned_projects.csv` (hand-built from state budget documents):

```csv
project_id,admin_code,sector,name,budget_inr_lakh,status,source,synthetic
MH-2026-001,IN-MH-NANDURBAR,water,Jal Jeevan multi-village scheme,1250,delayed,"Maharashtra budget 2026-27, Vol. X p. Y",false
```

`status`: `funded` / `sanctioned` / `in_progress` / `completed` count as funded; `delayed` / `stalled` as delayed.

After adding or changing files, from `backend/`:

```
python -m scripts.build_indicators --allow-placeholder
```

The build reports which metrics are still placeholders. Drop `--allow-placeholder` to make any gap an error.
