# Datasets

Anodet ships two **demo** files. Neither is a customer fleet.

| Path | Role |
|---|---|
| `data/cmapss/train_FD001.txt` | NASA C-MAPSS FD001 labeled sample. Default detector training set. |
| `data/demo/marine-diesel-sample.csv` | Shop-path sample (two diesel units, hours 1–45, healthy 1–20). |

Production history stays with the shop. Fit a customer CSV through the desk; later hours go through append. Do not mix scored output or SQLite dumps into this folder.

Override the NASA path with `ANODET_DATA` if you keep FD001 elsewhere. Do not commit large extra datasets or `audit.db`.
