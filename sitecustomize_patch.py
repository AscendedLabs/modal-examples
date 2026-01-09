import sys
from transformers import modeling_utils
sys.modules['transformers.modeling_layers'] = modeling_utils
