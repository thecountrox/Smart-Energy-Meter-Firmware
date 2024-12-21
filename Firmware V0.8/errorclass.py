class NewUpdateTime(Exception):
    def __init__(self, message):
      super().__init__("New Update Time: ", message)

    def stringify(self):
        string = f'Update Time:\n{self.message}'
        return string

# allows us to go out of this file and perform an update