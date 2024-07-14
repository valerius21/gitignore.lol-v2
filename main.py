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

IDEA_STRING = '''#  JetBrains specific template is maintained in a separate JetBrains.gitignore that can
#  be found at https://github.com/github/gitignore/blob/main/Global/JetBrains.gitignore
#  and can be added to the global gitignore or merged into this file.  For a more nuclear
#  option (not recommended) you can uncomment the following to ignore the entire idea folder.
.idea/'''

JETBRAINS_STRINGS = [
    'idea',
    'pycharm',
    'webstorm',
    'phpstorm',
    'rider',
    'goland',
    'intellij',
    'appcode',
    'clion',
    'datagrip',
    'resharper',
    'rustrover',
]

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


@app.get('/readyz')
async def readyz():
    """health check"""
    return {"status": "ok"}


@app.get('/{languages}')
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


@cache(expire=300)
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
    if lang in JETBRAINS_STRINGS:
        return IDEA_STRING
    if '.gitignore' not in lang:
        lang += '.gitignore'
    if lang not in file_list:
        raise HTTPException(status_code=404, detail="Could not find language file")

    with open(repo_path / lang.capitalize(), 'r') as file:
        content = file.read()
        return f'# ------------- {lang.capitalize()} -------------\n\n' + content


@cache(expire=300)
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
