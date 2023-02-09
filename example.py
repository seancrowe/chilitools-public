from chilitools.api.connector import ChiliConnector
from chilitools.utilities.ServerMigration import ServerMigrator

destChili = "https://ft-nostress.chili-publish.online/ft-nostress/interface.aspx"
srcChili = "https://cp-exp-123.chili-publish.online/cp-exp-123/interface.aspx"

c1 = ChiliConnector(backofficeURL=destChili, username="Name", password="pass1234", forceKeyRegen=True)
c2 = ChiliConnector(backofficeURL=srcChili, username="ChiliName", password="9a93f57c00c51b127e542", forceKeyRegen=True)
print(c2.getAPIKey())
print(c1.getAPIKey())

sm = ServerMigrator(directory="./", destChili=destChili, srcChili=srcChili)

sm.transferList(resource="documents", itemList=["1b422f7e-203f-4291-99e8-a5a269efe740"])