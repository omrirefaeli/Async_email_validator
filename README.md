# W_challenge

I wrote this project as part of an interview's home task. This is an asyncronous email addresses validator that checks existence of mass possible email addresses in a provided domain name.
The email addresses are generated according to several common patterns respectively for entities read in an input file with "first,last" names (as of now).

To avoid being blocked from the queried servers, a proxy option is available (socks4/socks5).

## Running
To make it convinent for you to check, just clone the repo, instantiate a virtual env using `poetry install` and run `main.py`.

If desired, the arguments that would have been provided via a theoretical calling function or command line arguments are at the top of the `main.py` file. 

## my env
I wrote this code using Python 3.7.9 and VSCode as my IDE.
