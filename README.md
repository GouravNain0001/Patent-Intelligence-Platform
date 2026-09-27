# Patent Intelligence Platform

A Python-based patent intelligence project for processing, searching, organizing, and exploring patent datasets using text processing, similarity analysis, and an interactive dashboard.

## Project Overview

The Patent Intelligence Platform is designed to work with patent data collected from structured XML and CSV sources. It provides a simple workflow for preprocessing patent data, storing relevant information, searching patent records, and identifying similar patent documents using text-based similarity techniques.

The project focuses on the **technical implementation of patent data processing and intelligence features**.

## Key Features

* Patent data processing from XML and CSV datasets
* Data cleaning and preprocessing using Pandas
* Patent record search and filtering
* TF-IDF-based text representation
* Text similarity analysis using Scikit-learn
* Structured patent data storage
* Interactive Streamlit dashboard
* Exploration of related patent documents

## Technologies Used

* **Python**
* **Pandas**
* **Scikit-learn**
* **Streamlit**
* **MySQL / Database**
* **XML & CSV Processing**
* **TF-IDF / Text Similarity**

## Project Structure

```text
Patent_Intelligence_Platform/
│
├── dashboards/
│   └── app.py
│
├── database/
│   └── patent_database.py
│
├── python/
│   ├── import_recent_patents.py
│   ├── load_patents.py
│   ├── parse_patents.py
│   ├── preprocess_patents.py
│   ├── search_patents.py
│   └── similarity_engine.py
│
├── data/
│   ├── clean_patents.csv
│   ├── processed_patents.csv
│   └── raw_patents.csv
│
├── .gitignore
└── README.md
```

## Workflow

```text
Patent Dataset
      ↓
XML / CSV Processing
      ↓
Data Parsing
      ↓
Data Preprocessing
      ↓
Patent Search
      ↓
TF-IDF Text Representation
      ↓
Similarity Analysis
      ↓
Streamlit Dashboard
```

## How It Works

### 1. Data Processing

Patent data is parsed from structured sources and converted into a usable tabular format.

### 2. Preprocessing

The data is cleaned and prepared for further search and text analysis using Python and Pandas.

### 3. Patent Search

The search module allows users to search and explore patent records based on available textual information.

### 4. Similarity Analysis

TF-IDF is used to represent patent text numerically, followed by text similarity analysis using Scikit-learn to identify related documents.

### 5. Dashboard

A Streamlit-based interface provides an interactive way to explore patent data and analysis results.

## Installation

Clone the repository:

```bash
git clone https://github.com/GouravNain0001/Patent-Intelligence-Platform.git
cd Patent-Intelligence-Platform
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install the required libraries:

```bash
pip install pandas scikit-learn streamlit
```

## Run the Application

From the project root directory:

```bash
python -m streamlit run dashboards/app.py
```

The Streamlit application will open in your browser.

## Note on Dataset

The original large XML patent dataset is **not included in this repository** because of its large file size. The repository contains the processed datasets required for demonstrating the project functionality.

## Learning Objective

This project was developed to gain practical experience in:

* Patent data handling
* Text preprocessing
* Information retrieval concepts
* Text similarity
* Data analysis with Python
* Building interactive analytical dashboards
* Working with structured technical datasets

## Future Improvements

* Integration with larger patent databases
* Advanced semantic similarity using transformer-based models
* Improved p
