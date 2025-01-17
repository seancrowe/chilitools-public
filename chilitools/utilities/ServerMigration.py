import os
import base64
from time import sleep
from chilitools.api.connector import ChiliConnector
from chilitools.utilities.file import writeFile, readFile, checkForFile
from chilitools.utilities.backoffice import backofficeURLInput
from chilitools.utilities.logger import getLogger
from chilitools.utilities.document import ChiliDocument


class ServerMigrator:
  def __init__(self, directory: str, verbose: bool = False, update: bool = False, srcChili: str = None, destChili: str = None):
    # Try to load the progress JSON file
    self.progressFile = directory+'/progress.json'
    if checkForFile(fileName=self.progressFile):
      print("Found progress file for server migration, loading it.")
      self.progress = readFile(fileName=self.progressFile, isJSON=True)
      self.source = ChiliConnector(backofficeURL=self.progress['sourceURL'])
      self.dest = ChiliConnector(backofficeURL=self.progress['destURL'])
    else:
      # progress JSON not found
      if srcChili is None:
        print("-------------SOURCE CHILI BACKOFFICE URL---------------")
        srcChili = backofficeURLInput()
      if destChili is None:
        print("-------------DESTINATION CHILI BACKOFFICE URL---------------")
        destChili = backofficeURLInput()
      self.source = ChiliConnector(backofficeURL=srcChili)
      self.dest = ChiliConnector(backofficeURL=destChili)
      self.progress = {'sourceURL': srcChili, 'destURL': destChili, 'resources':{}}
      self._saveProgressFile()

    self.directory = directory
    self.logger = getLogger(directory+'/ServerMigrator.log')
    self.verbose = verbose
    self.interval = 1
    self.update = update

  def getResourceTrees(self):
    self.logger.info("Getting list of resource items")
    resources = set()
    r = self.source.resources.getResourceList().content
    for item in r['resources']['item']: resources.add(item['@name'].lower())
    for resource in resources:
      if not resource in self.progress['resources'].keys() or self.update:
        self.getResourceTree(resource)
      elif self.verbose: print(f"Already found resource tree for {resource}. Pass the update=True arg to force update")

  def getResourceTree(self, resource: str, parentFolder: str = ''):
    resource = resource.lower()
    self.logger.info(f"Getting resource tree for {resource}.. This may take some time depending on size")
    resp = self.source.resources.ResourceGetTreeLevel(resourceType=resource, parentFolder=parentFolder, numLevels=-1, includeSubDirectories=True)
    if resp.success:
      path = f"{self.directory}/{resource}/{resource}.json"
      writeFile(fileName=path, data=resp.content, isJSON=True)
      self.progress['resources'][resource] = {'treeFile': path}
      self._saveProgressFile()
    else:
      self.logger.error(resp.asDict())

  def transferAll(self):
    for resource in self.progress['resources'].keys():
      self.transferResource(resource)

  def transferList(self, resource: str, itemList: str):
    resource = resource.lower()

    if resource not in self.progress['resources'].keys():
      self.progress['resources'][resource] = {'toTransfer':[]}

    # Check if there are items still in the transfer queue from a previous transfer
    if 'toTransfer' in self.progress['resources'][resource].keys() and len(self.progress['resources'][resource]['toTransfer']) > 0:
      self.logger.info(f'Found {resource} still queued to be transferred from previously')
      self.__transferItems(resource)
    else:
      for item in itemList:
        if self.verbose:
          self.logger.info(f"Getting item definition XML for ID: {item}")
        resp = self.source.resources.ResourceItemGetDefinitionXML(
          resourceType=resource,
          itemID=item
        )
        if not resp.success:
          if resource.lower() == "fonts":
            self.logger.warn(f"There was an issue getting item definition for {resource} with id: {item}")
          else:
            self.logger.error(f"There was an issue getting item definition for {resource} with id: {item}")
          if self.verbose:
            print(resp.asDict())
        else:
          itemXML = resp.contentAsDict()['item']
          itemXML['@path'] = itemXML['@relativePath']
          self.progress['resources'][resource]['toTransfer'].append(itemXML)
          #self._saveProgressFile()
      self.__transferItems(resource=resource, disablePreviews=False)

  def transferResource(self, resource: str, parentFolder: str = '', customPath: str = None):
    resource = resource.lower()
    if not resource in self.progress['resources'].keys() or self.update or 'treeFile' not in self.progress['resources'][resource].keys():
      self.logger.info(f'Updating {resource} directory tree structure')
      self.getResourceTree(resource, parentFolder)

    # Check if there are items still in the transfer queue from a previous transfer
    if 'toTransfer' in self.progress['resources'][resource].keys() and len(self.progress['resources'][resource]['toTransfer']) > 0:
      self.logger.info(f'Found {resource} still queued to be transferred from previously')
      self.__transferItems(resource)
    else:
      self.progress['resources'][resource]['toTransfer'] = []
      filePath = self.progress['resources'][resource]['treeFile']
      if checkForFile(fileName=filePath):
        items = readFile(self.progress['resources'][resource]['treeFile'], isJSON=True)
        #print(f"ITEMS: \n {items['tree']}\n\n")
        if 'item' in items['tree']:
          self.__iterresource(resource, items['tree']['item'], customPath)
          self._saveProgressFile()
          self.__transferItems(resource)
        else:
          self.logger.info(f'There are no items to transfer for the {resource} resource')
      else:
        self.logger.info('The file path for the resource tree indicated in the progress file could not be found on the system. Going to update resource tree')
        self.getResourceTree(resource)
        self.transferResource(resource)

  def __transferItems(self, resource: str, disablePreviews: bool = True):
    resource = resource.lower()
    items = self.progress['resources'][resource]['toTransfer']
    if len(items) > 0:

      if disablePreviews:
        # Turn off Automatic Preview Generation for the API KEY
        resp = self.dest.system.SetAutomaticPreviewGeneration(createPreviews=False)
        if not resp.didSucceed():
          # self.logger.error(f"There was an issue disabling the automatic preview generation for the CHILI Destination Server API Key")
          pass
        elif self.verbose:
          print(f"\n{resp.text}\n")

      itemList = items.copy()
      itemAmount = len(itemList)
      self.logger.info(f'Amount of {resource} to transfer: {itemAmount}')
      for r in itemList:
        if self.verbose:
          print(f"Name: {r['@name']}\nID: {r['@id']}\nPath: {r['@path']}\nDownload URL: {self.getDownloadURL(resource, r['@id'])}\n")

        # Set ID for the next item
        self.logger.info(f"Setting the ID for the next uploaded item to: {r['@id']}")
        resp = self.dest.resources.setNextResourceItemID(resourceType=resource, itemID=r['@id'])
        if not resp.didSucceed():
          self.logger.error(f"There was an issue setting the next item ID for {r['@name']}: {r['@id']}\n{resp.text}")
          continue
        elif self.verbose:
          print(f"\n{resp.text}\n")

        if not "finished=\"True\"" in resp.text:
          self.logger.warn(f"Skipping item because item ID already exists for {r['@name']}: {r['@id']}")
          continue

        # Extract path from resource tree item (orginal path is full path ending with <document name>.xml)
        if len(r['@path']) != 0:
          splitPath = r['@path'].split("\\")
          fileName = splitPath.pop()
          resourceItemPath = "\\".join(splitPath)+"\\"
        else:
          resourceItemPath = ''

        # IF ASSET = NEED TO USE MACHINE AS MIDDLEMAN
        if resource.lower() == 'assets':
          # Download Asset
          self.logger.info(f"Downloading asset file data temporarily for: {r['@name']}")
          fileData = self.source.resources.DownloadAsset(
            resourceType='assets',
            id=r['@id'],
            itemPath=r['@path'],
            assetType='original',
            page=1
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue downloading the asset - Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

          # Base64 Encode the byte data
          fileData = base64.b64encode(fileData.response.content)
          fileData = fileData.decode('utf-8')

          self.logger.info(f"Uploading asset data to destination CHILI server: {r['@name']}")
          resp = self.dest.resources.ResourceItemAdd(
            resourceType='assets',
            newName=fileName,
            fileData=fileData,
            xml='',
            folderPath=resourceItemPath
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue uploading the asset to the destination server- Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

          itemSizeDest = self.dest.resources.ResourceItemGetDefinitionXML(resourceType="assets", itemID=r['@id'])
          itemSizeSrc = self.source.resources.ResourceItemGetDefinitionXML(resourceType="assets", itemID=r['@id'])

          # Check file size
          if itemSizeSrc.data['item']['fileInfo']['@fileSize'] != itemSizeDest.data['item']['fileInfo']['@fileSize']:
            self.logger.error(f"Asset wrong size from dest to src - Name: {r['@name']} -- Item ID: {r['@id']}\n")
         

        # IF ASSET = NEED TO USE MACHINE AS MIDDLEMAN
        elif resource.lower() == 'fonts':
          # Download Asset
          self.logger.info(f"Downloading fonts file data temporarily for: {r['@name']}")
          fileData = self.source.resources.DownloadAsset(
            resourceType='fonts',
            id=r['@id'],
            itemPath=r['@path'],
            assetType='original',
            page=1
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue downloading the fonts - Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

          # Base64 Encode the byte data
          fileData = base64.b64encode(fileData.response.content)
          fileData = fileData.decode('utf-8')

          self.logger.info(f"Uploading fonts data to destination CHILI server: {r['@name']}")
          resp = self.dest.resources.ResourceItemAdd(
            resourceType='fonts',
            newName=fileName,
            fileData=fileData,
            xml='',
            folderPath=resourceItemPath
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue uploading the fonts to the destination server- Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

        elif resource.lower() == "documents":
          # Download document
          self.logger.info(f"Downloading documents file data temporarily for: {r['@name']}")
          fileData = self.source.resources.DownloadAsset(
            resourceType='documents',
            id=r['@id'],
            itemPath=r['@path'],
            assetType='original',
            page=1
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue downloading the document - Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

          docXml = fileData.response.text

          if (docXml == "Item not found"):
            self.logger.error(f"Document not found - Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

          cd = ChiliDocument(docXml)

          fonts = []
          for font in cd.get_fonts():
            fonts.append(font["id"])

          print(fonts)
          self.transferList(itemList=fonts, resource="Fonts")

          images = []
          for image in cd.get_images():
            if image["resource_type"] == "Assets":
              images.append(image["id"])

          self.transferList(itemList=images, resource="Assets")

          # Create a placeholder document because if you ResourceItemAdd a document, CHILI will process the XML and will remove spaces
          self.logger.info(f"Creating placeholder document to destination CHILI server: {r['@name']}")
          resp = self.dest.resources.ResourceItemAdd(
            resourceType='documents',
            newName=fileName,
            fileData="<document />",
            xml='',
            folderPath=resourceItemPath
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue creating a placeholder document to the destination server- Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

          writeFile(fileName="./response.txt", data=fileData.response.text, encoding="utf-8")

          self.logger.info(f"Uploading document data to destination CHILI server: {r['@name']}")
          resp = self.dest.resources.ResourceItemSave(
            itemID=r['@id'],
            resourceType="documents",
            xml=docXml,
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue uploading the document to the destination server- Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue

        else:
          # Items other than assets
          # Transfer the item
          resp = self.dest.resources.ResourceItemAddFromURL(
            resourceType=resource,
            newName=r['@name'],
            folderPath=resourceItemPath,
            url=self.getDownloadURL(resource, r['@id']),
            reuseExisting=True
          )
          if not resp.didSucceed():
            self.logger.error(f"There was an issue adding the item - Name: {r['@name']} -- Item ID: {r['@id']}\n{resp.text}")
            continue
          elif self.verbose:
            print(f"\n{resp.text}\n")

        # Set a pause to avoid overwhelming the server.
        self.logger.info(f"Successfully transferred Name: {r['@name']} - ID: {r['@id']} to the destination CHILI server.")
        itemAmount = itemAmount - 1
        self.logger.info(f"Waiting {self.interval} seconds to avoid server stress. There are {itemAmount} resources left")
        self.progress['resources'][resource]['toTransfer'].remove(r)
        self._saveProgressFile()
        sleep(self.interval)

      if disablePreviews:
        # Turn back on the Automatic Preview Generation for the API KEY
        resp = self.dest.system.SetAutomaticPreviewGeneration(createPreviews=True)
        if not resp.didSucceed():
          self.logger.error(f"There was an issue re-enabling the automatic preview generation for the CHILI Destination Server API Key")
        elif self.verbose:
          print(f"\n{resp.text}\n")

    else:
      self.logger.info(f'There is nothing queued to transfer for the {resource} resource')


  def __iterresource(self, resource: str, d, customPath: str = None):
    for v in d:
      # Folder item is going to be a list
      # file item is going to be a dict with the info
      if isinstance(v, dict):
        if '@isFolder' in v.keys():
          if v['@isFolder'] == 'true':
            if 'item' in v.keys():
              if isinstance(v['item'], dict): v['item'] = [v['item']]
              self.__iterresource(resource, v['item'])
            else:
              #Empty folder
              pass
          else:
            if customPath is not None:
              v['@path'] = customPath
            self.progress['resources'][resource]['toTransfer'].append(v)
            if self.verbose:
              self.logger.info(f"Adding {v} to the transfer queue")
      elif isinstance(v, str):
        if isinstance(d[v], list):
          self.__iterresource(resource, d[v])

  def getDownloadURL(self, resource: str, itemID: str):
    downloadURL =  self.source.baseURL + self.source.enviroment + '/download.aspx?type=original&resourceName=' + resource + '&id=' + itemID + '&apiKey=' + self.source.getAPIKey() + '&pageNum=1'
    return downloadURL

  def _saveProgressFile(self):
    writeFile(fileName=self.progressFile, data=self.progress, isJSON=True)
