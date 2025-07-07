# 🧾 PDF Claims Extractor

This project automates the extraction of **medical claims** and **benefits summaries** from scanned insurance PDF documents using OCR and structured table parsing. It outputs the processed data in a Python `pickle` file format and stores it in Redis for downstream consumption.

---

## 📦 Features

- **OCR-based PDF Table Extraction** using [Camelot](https://camelot-py.readthedocs.io/)
- Extracts and processes two key datasets:
  - `claims` table: Monthly claim records
  - `benefits` table: Benefit-wise summary
- Adds metadata from the document:
  - `Policy Year`, `End_Date`, `Class`, `Overall_Limit`
- Stores results as:
  ```python
  {
    "claim_experiences": {
        "claims": claims_df,
        "benefits": benefits_df
    }
  }
  ```
-  Redis integration to persist structured output
-  Fully containerized using Docker + Docker Compose

---

## 🚀 Getting Started

### 🔧 Prerequisites

Ensure you have the following installed:

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

---

### ⚙️ Run the Extraction Pipeline

```bash
docker compose up --build
```

This command will:

1. Build the image for the extractor
2. Start a Redis container
3. Execute the extraction logic inside the container
4. Save output in:
   - `dataframes.txt` (Pickle file)
   - Redis (`pdf_extraction_results` key)

---

Docker image: https://hub.docker.com/r/nourwork/pdf-claims-extractor
---

## 📁 Output File

### `dataframes.txt`

Pickled Python dictionary with this structure:

```python
{
  "claim_experiences": {
      "claims": <pandas.DataFrame>,
      "benefits": <pandas.DataFrame>
  }
}
```

You can verify it manually by running:

```python
import pickle

with open("dataframes.txt", "rb") as f:
    data = pickle.load(f)

print(data["claim_experiences"]["claims"].head())
print(data["claim_experiences"]["benefits"].head())
```

---

## 📊 Output Schema

### `claims` DataFrame

| Column                         | Description                            |
|--------------------------------|----------------------------------------|
| Monthly claims                 | Month label (e.g., Jan-2023)           |
| Number of insured lives        | Number of insured individuals          |
| Number of claims               | Count of claims filed                  |
| Amount of paid claims          | Amount paid for claims                 |
| Amount of paid claims (with VAT) | Including VAT                       |
| Policy Year                    | `Prior Policy Year` / `Last Policy Year` |
| End_Date                       | Extracted from metadata                |
| Class                          | Extracted from metadata                |
| Overall_Limit                  | Extracted from metadata                |

---

### `benefits` DataFrame

| Column                       | Description                             |
|------------------------------|-----------------------------------------|
| Benefit_Sama                 | Benefit type (e.g., Outpatient)         |
| Number of Claims             | Number of claims                        |
| Amount of Claims             | Total amount paid                       |
| Amount of Claims with VAT    | Including VAT                           |
| Notes                        | Deductible or special limits if present |
| Policy Year                  | `Last Policy Year`                      |
| End_Date                     | Extracted from metadata                 |
| Class                        | Extracted from metadata                 |
| Overall_Limit                | Extracted from metadata                 |


---

## 📂 Project Structure

```
pdf-claims-extractor/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pdf_extractor.py
├── driver.py
├── OCR_Test.pdf
├── dataframes.txt
└── README.md
```

---

## 🛠️ Notes

- **Camelot** requires `ghostscript` and `poppler` for table parsing from PDFs.
- Metadata is extracted using regex from free-text blocks in the PDF.
- Redis is used for temporary storage of the results but is optional for future integration.

---

## 👨‍💻 Author

This project was developed as part of an OCR-based PDF processing assignment.  
For technical questions or maintenance, contact:

**Name:** Nour AL-Smadi
**Email:** nooralsmadi173@gmail.com

---

## 📜 License

This project is provided for educational and internal use only.
