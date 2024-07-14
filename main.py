from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from fastapi_utilities import repeat_every
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
    return {"available": [f.replace(".gitignore", "") for f in files]}


@app.get('/{languages}')
@cache(expire=300)
async def get_language_ignore_file(languages: str):
    langs = languages.lower().strip()
    if ',' in langs:
        langs = langs.split(',')
    else:
        langs = [langs]

    # filter out empty strings
    langs = [lang for lang in langs if lang]
    if not langs:
        raise HTTPException(status_code=400, detail="No languages provided")

    repo_path = Path(REPO_DIR)
    file_list = await get_file_list()

    contents = []
    for lang in langs:
        contents.append(await get_file_contents(lang, repo_path, file_list))
    joined_contents = await post_process_contents(contents)
    return PlainTextResponse(joined_contents, media_type='text/plain')


async def get_file_list():
    repo_path = await check_repository()
    if repo_path is None:
        raise HTTPException(status_code=500, detail="Could not find repository")
    # list all files in the repository
    file_list = list(repo_path.glob('*.gitignore'))
    # convert to lowercase
    return [file.name.lower() for file in file_list]


async def check_repository() -> Path | None:
    repo_path = Path(REPO_DIR)
    if not repo_path.exists():
        try:
            await update_repository()
            return repo_path
        except Exception as e:
            print(e)
            return None
    return repo_path


@cache(expire=300)
async def get_file_contents(lang: str, repo_path: Path, file_list: List[str]) -> str:
    if '.gitignore' not in lang:
        lang += '.gitignore'
    if lang not in file_list:
        raise HTTPException(status_code=404, detail="Could not find language file")

    with open(repo_path / lang.capitalize(), 'r') as file:
        content = file.read()
        return f'# ------------- {lang.capitalize()} -------------\n\n' + content


async def post_process_contents(contents: List[str]) -> str:
    joined_contents = '\n'.join(contents)
    lines = joined_contents.splitlines()
    occurred_lines = {}

    for i, line in enumerate(lines):
        if line in occurred_lines:
            lines[i] = ""
        else:
            occurred_lines[line] = True
    return '\n'.join(lines)
