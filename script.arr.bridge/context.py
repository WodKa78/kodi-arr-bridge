import sys
from resources.lib.app import main

if __name__ == '__main__':
    main(['action=add'], getattr(sys, 'listitem', None))
