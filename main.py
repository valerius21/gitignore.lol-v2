from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_utilities import repeat_every
from fastapi_cache.decorator import cache

from git import Repo

REPO_URL = "https://github.com/github/gitignore.git"
REPO_DIR = "ignore_files"

app = FastAPI()


@app.on_event('startup')
@repeat_every(seconds=60 * 60 * 24)
async def update_repository():
    FastAPICache.init(InMemoryBackend())
    repo_path = Path(REPO_DIR)
    if repo_path.exists():
        repo = Repo(REPO_DIR)
        repo.remotes.origin.pull()
    else:
        Repo.clone_from(REPO_URL, REPO_DIR)


@app.get("/")
@cache(expire=300)
async def root():
    files = await get_file_list()
    return {"available": f.replace(".gitignore", "") for f in files}


@app.get('/{lang}')
@cache(expire=300)
async def get_language_ignore_file(lang: str):
    lang = lang.lower()
    repo_path = Path(REPO_DIR)
    file_list = await get_file_list()

    # if lang does not include .gitignore, add it
    if '.gitignore' not in lang:
        lang += '.gitignore'

    # if lang is not in the list of files, return an error
    if lang not in file_list:
        return {'status': 'error. Could not find language file'}

    # open the file and return its contents
    with open(repo_path / lang, 'r') as file:
        # return the contents of the file as plain text
        contents = file.read()

    return PlainTextResponse(contents, media_type='text/plain')


async def get_file_list():
    repo_path = Path(REPO_DIR)
    if not repo_path.exists():
        try:
            await update_repository()
        except Exception as e:
            print(e)
            return {'status': 'error'}
        if not repo_path.exists():
            return {'status': 'error. Could not find repository'}

    # list all files in the repository
    file_list = list(repo_path.glob('*.gitignore'))
    # convert to lowercase
    return [file.name.lower() for file in file_list]
