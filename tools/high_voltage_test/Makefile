#you have to make sure you have following tools
#	1>python3.7
#	2>pipenv
#	3>make


main := $(abspath main.py)
gpt:= $(abspath GptDevice.py)
python := $(dirname ../.local/share/virtualenvs/High_Voltage_Test-C8TIcr5A/Scripts/python3 )


setup:
	pipenv install

pip:
	pipenv run pip3 list


run: setup
	pipenv run $(python) $(main)


gpt: setup
	pipenv run $(python) $(gpt)

show:
	echo $(python)
	echo $(main)
	#echo $(PATH)


