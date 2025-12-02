import os
import sys
import threading
import time
from app.brain import Brain
from app.gui.interface import Interface
from app.gui.face import Rosto
from app.core.audio import AudioHandler
import config


app_visual = Interface()
app_brain = Brain()
app_audio = AudioHandler()


