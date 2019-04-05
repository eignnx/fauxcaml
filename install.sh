echo 'Installing fauxcaml compiler...'

echo 'Saving current working directory...'
fauxcaml_root=`pwd`

if ! [ -f /usr/local/bin/python3.7 ]
then
    echo 'ERROR: Python 3.7 must be installed and located at `/usr/local/bin/python3.7`!'
    echo 'Aborting installation...'
    exit 1
fi

if ! [ -d venv ]
then
    echo 'Setting up a python virtual environment...'
    /usr/local/bin/python3.7 -m venv venv
fi

if ! [ -f ./venv/bin/activate ]
then
    echo 'ERROR: Something went wrong creating the virtual environment. Cannot find activation script which ought to be located at `venv/bin/activate`.'
    echo 'Aborting installation...'
    exit 1
fi

source ./venv/bin/activate
echo 'Installing python dependencies...'
pip install -r requirements.txt

echo 'Generating `fauxcamlc` script...'
sed "s#{{}}#${fauxcaml_root}#" .fauxcamlc.template.sh > fauxcamlc
chmod a+x fauxcamlc

echo
echo 'Fauxcaml compiler installed as `fauxcamlc`.'
echo
echo "I recommend putting \`fauxcamlc\` in \`/usr/local/bin\` so that it's accessable from anywhere. To do so, execute the following commands:"
echo
echo '    $ sudo cp fauxcamlc /usr/local/bin/fauxcamlc'
echo '    $ sudo chmod a+x /usr/local/bin/fauxcamlc'
echo
read -p 'Would you like me to run those two commands for you? [Y/N] ' ans

if [ "${ans^^}" = 'Y' ]
then
    echo
    echo 'Moving `fauxcamlc` into `/usr/local/bin`...'
    sudo cp fauxcamlc /usr/local/bin/fauxcamlc
    echo 'Setting executable permissions on `/usr/local/bin/fauxcamlc`...'
    sudo chmod a+x /usr/local/bin/fauxcamlc
else
    echo
    echo "Ok. I won't run the commands. You will need to specify the full path to \`fauxcamlc\` in order to use it."
fi

echo
echo 'Installation complete.'

