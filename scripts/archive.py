import sys
import subprocess
from pathlib import Path

dir_arg = sys.argv[1] if len(sys.argv) > 1 else '.'
dir_path = Path(dir_arg).resolve()

output = f'{dir_path.name}.zip'

subprocess.run(['git-archive-all', '-C', str(dir_path), output], check=True)
