export PYTHONPATH="."

python test/mock_server.py 2>/dev/null &
PID=$!

if [ -n "${COVER_DIR}" ]; then
	COVERAGE="--with-coverage --cover-erase --cover-html --cover-html-dir=${COVER_DIR}";
else
	COVERAGE=''
fi;

echo Starting mock server pid ${PID}
#pyvows test/
nosetests --with-doctest --with-freshen -v $@

echo Killing mock server pid ${PID}
kill $PID
