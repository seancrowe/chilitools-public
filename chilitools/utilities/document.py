from lxml import etree

class ChiliDocument:
  def __init__(self, doc_xml: str):
    try:
      self.doc: etree._Element = etree.fromstring(doc_xml)
      self.name = self.get_name()
      self.id = self.get_id()
    except Exception as e:
      print(f"There was an error creating a Document from the XML")

  def to_xml(self) -> str:
    return etree.tostring(self.doc, method="xml")

  def get_name(self):
    if self.doc is None: return
    return self.doc.attrib.get('name')

  def get_id(self):
    if self.doc is None: return
    return self.doc.attrib.get('id')

  def get_fonts(self):
    if self.doc is None: return
    fonts = []

    for font in self.doc.findall("fonts//"):
      fonts.append({
        "resource_type": "Fonts",
        "id": font.get("id"),
        "name": font.get("name"),
        "family": font.get("family"),
        "style": font.get("style")
      })

    return fonts

  def get_images(self):
    if self.doc is None: return
    images = []

    for image_frame in self.doc.findall("pages//item[@type='image']"):
      if image_frame.get("hasContent", "false") == "true":
        if len(image_frame.get("dynamicAssetProviderID", "")) > 1:
          images.append({
            "resource_type": "DynamicAssetProviders",
            "id": image_frame.get("dynamicAssetProviderID")
          })
        else:
          images.append({
            "resource_type": "Assets",
            "id": image_frame.get("externalID"),
            "name": image_frame.get("externalName", ""),
            "path": image_frame.get("path", "")
          })

    for inline_image_frame in self.doc.findall(".//frame[@type='image']"):
      if  inline_image_frame.get("hasContent", "false") == "true":
        if len( inline_image_frame.get("dynamicAssetProviderID", "")) > 1:
          images.append({
            "resource_type": "DynamicAssetProviders",
            "id":  inline_image_frame.get("dynamicAssetProviderID")
          })
        else:
          images.append({
            "resource_type": "Assets",
            "id":  inline_image_frame.get("externalID"),
            "name":  inline_image_frame.get("externalName", ""),
            "path":  inline_image_frame.get("path", "")
          })


    return images
