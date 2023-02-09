# Chilitools Migration

This is project forked from Austin's project https://github.com/austin-meier/chilitools-public that is specifically focused on migration.

Some of the fixes brought here will be pushed back to Austin's project

Requires Python >= 3.8

# Instructions

1. Download the project with `git clone`
2. Install dependencies
    - You can use PDM, and run `pdm install`
    - Another option is to look through the pyproject.toml file and see what packages to install with pip
3. Open example.py, and change the file to match your needs
    - Update `destChili` and `srcChili`
    - Update username and password for each initialization of ChiliConnector
4. Run example.py - if you are using PDM, you need to run using `pdm run example.py`. If you used plan old `pip` then you can just `python example.py`


## Do Not!
Do not use chilitools on PyPi. It is using a slightly different source than what has been done here.



