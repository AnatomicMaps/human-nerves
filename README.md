# human-nerves

Repository to archive and share information about the human nerves.

Instructions:

1. Create a virtul environment :
   e.g.`pyenv virtualenv 3.12 human-nerves-env`
2. Activate the virtual environment
   e.g. `pyenv activate human-nerves-env`
3. Install required libraries
   e.g. `pip install -r requirements.txt`
4. Don't forget to export SCICRUNCH_API_KEY password
   e.g. `export SCICRUNCH_API_KEY=XXXXX`
5. All god now, run `jupyter notebook` from terminal and then open `reroute.ipynb`.

Checking current coverage:

```
python nerve-testing.py sckan-2024-09-21 nerve_point_annotations.json M2.6_3D_whole-body.csv
```

params:

- sckan-version
- nerve point annotation (manInBox) file
- nerve pathway file
