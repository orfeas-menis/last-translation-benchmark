# push to remote
rsync -azP --filter=":- .gitignore" --exclude .git/ . ltb:/home/zouhar/last-translation-benchmark/