from pdf_extractor import PDFTableExtractor

if __name__ == "__main__":
    ext = PDFTableExtractor(redis_host="redis", redis_port=6379)
    ext.run("OCR_Test.pdf")
