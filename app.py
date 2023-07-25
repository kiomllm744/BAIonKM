# Import necessary modules from Flask, SQLAlchemy, and other libraries
from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import secrets
import pandas as pd
import json
import requests
from sqlalchemy import func

# Create a Flask application instance
app = Flask(__name__)

# Configure and set up the database
secret_key = secrets.token_hex(32)
app.config['SECRET_KEY'] = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diseaseportal.db'
db = SQLAlchemy(app)
engine = create_engine('sqlite:///diseaseportal.db')
Session = sessionmaker(bind=engine)

# Define SQLAlchemy models for the Disease and Herb tables


class Disease(db.Model):
    __tablename__ = 'diseases'
    Serial_Number_D = db.Column(db.INTEGER, primary_key=True, autoincrement=True)
    geneNID = db.Column(db.TEXT)
    diseaseNID = db.Column(db.TEXT)
    diseaseId = db.Column(db.TEXT)
    geneId = db.Column(db.TEXT)
    diseaseName = db.Column(db.TEXT)
    geneName = db.Column(db.TEXT)
    score = db.Column(db.TEXT)


class Herb(db.Model):
    __tablename__ = 'herbs'
    Serial_Number_H = db.Column(db.INTEGER, primary_key=True, autoincrement=True)
    Compound = db.Column(db.TEXT)
    TCMID_ID = db.Column(db.TEXT)
    Genes = db.Column(db.TEXT)
    GeneId = db.Column(db.TEXT)
    herbName = db.Column(db.TEXT)


def search_disease(disease_name):
    session = Session()
    matching_records = session.query(Disease).filter(Disease.diseaseName.ilike(disease_name.lower())).all()
    session.close()
    disease_gene_symbols = [record.geneName for record in matching_records]
    return disease_gene_symbols


def search_herb_directory(herb_names):
    session = Session()
    single_herb_list_gene_symbols = []
    missing_herbs = []  # List to store missing herbs

    for herb_name in herb_names:
        # Assuming herb_name contains the input term
        herb_records = session.query(Herb).filter(func.lower(Herb.herbName) == herb_name.lower()).all()
        gene_symbols = [record.Genes for record in herb_records]
        # print(herb_name)
        # print(len(gene_symbols))

        if not gene_symbols:  # If the list is empty, the herb is not found in the database
            missing_herbs.append(herb_name)
        else:
            # Extend the single_herb_list_gene_symbols with the gene_symbols list directly
            single_herb_list_gene_symbols.extend(gene_symbols)

    session.close()

    if missing_herbs:
        # Display a message or log the missing herbs
        print(f"The following herbs were not found in the database: {', '.join(missing_herbs)}")

    return single_herb_list_gene_symbols



def find_common_genes(disease_gene_names, all_herbs_gene_symbols):
    all_common_genes = []  # List to store the common genes for each herb set

    for i, single_herb_list_gene_symbols in enumerate(all_herbs_gene_symbols):
        # Convert the gene symbols lists to sets for efficient intersection operation
        disease_genes_set = set(disease_gene_names)
        single_herb_genes_set = set(single_herb_list_gene_symbols)

        common_genes = disease_genes_set & single_herb_genes_set  # Find common elements
        # print(len(common_genes))

        # Add the common genes for the current herb set to the list
        all_common_genes.append(list(common_genes))

    return all_common_genes


def find_unique_genes(all_common_genes):
    unique_genes = set(all_common_genes[0])  # Initialize with the genes from the first list
    all_unique_genes = []  # Main list to store unique genes for all herb lists

    # Compare with the genes from the other lists
    for common_genes in all_common_genes[1:]:
        unique_genes -= set(common_genes)

    for i, genes in enumerate(all_common_genes):
        herb_list_index = i + 1
        unique_genes_for_list = set(genes) - set().union(*all_common_genes[:i], *all_common_genes[i + 1:]) if len(
            all_common_genes) > 1 else set(genes)
        print(unique_genes_for_list)
        print(len(unique_genes_for_list))
        all_unique_genes.append(unique_genes_for_list)  # Append unique genes to the main list

    return all_unique_genes


def upload_gene_lists(gene_lists):
    ENRICHR_URL = 'https://maayanlab.cloud/Enrichr/addList'
    all_data = []  # Collect the results for each gene list

    for gene_list in gene_lists:
        genes_str = "\n".join(list(gene_list))
        payload = {
            'list': (None, genes_str),
        }
        response = requests.post(ENRICHR_URL, files=payload)
        if not response.ok:
             raise Exception('Error analyzing gene list')
        data = json.loads(response.text)
        all_data.append(data)

    return all_data




def enrichment_analysis(data_list, library):
    ENRICHR_URL = 'https://maayanlab.cloud/Enrichr/enrich'
    query_string = '?userListId=%s&backgroundType=%s'
    gene_set_library = library

    for data in data_list:
        user_list_id = data['userListId']
        response = requests.get(ENRICHR_URL + query_string % (user_list_id, gene_set_library))
        if not response.ok:
            raise Exception(f"Error fetching enrichment results for userListId: {user_list_id}")

        enrichment_data = json.loads(response.text)
        df = pd.DataFrame(enrichment_data)

        # Column names for the new DataFrame
        column_names = ['Rank', 'Term name', 'P-value', 'Z-score', 'Combined score', 'Overlapping genes',
                        'Adjusted p-value', 'Old p-value', 'Old adjusted p-value']

        # Create an empty DataFrame to store the enrichment data for the current herb set
        data['enrichment_data'] = []

        # Iterate over the rows in the DataFrame
        for _, row in df.iterrows():
            for element in row:
                # Extract the values from the element
                rank = element[0]
                term_name = element[1]
                p_value = element[2]
                z_score = element[3]
                combined_score = element[4]
                overlapping_genes = ', '.join(element[5])
                adjusted_p_value = element[6]
                old_p_value = element[7]
                old_adjusted_p_value = element[8]

                # Check if the adjusted_p_value is greater than 0.01
                if adjusted_p_value < 0.05:
                    # Create a new row with extracted values
                    new_row = pd.DataFrame([[rank, term_name, p_value, z_score, combined_score, overlapping_genes,
                                             adjusted_p_value, old_p_value, old_adjusted_p_value]],
                                           columns=column_names)

                    # Append the new row to the enrichment data for the current herb set
                    data['enrichment_data'].append(new_row.to_dict(orient='records')[0])

        # Filter the enrichment data to get only the top 15 entries with adjusted_p_value > 0.01
        data['enrichment_data'] = data['enrichment_data'][:15]

    return data_list



# Route handler for the homepage
@app.route('/')
def index():
    return render_template('index.html')

# Route handler for form submission
# Route handler for form submission


@app.route('/submit', methods=['POST'])
def submit_form():
    if request.method == 'POST':
        # Get the user input from the submitted form
        disease_name = request.form['disease']
        herbs_data_json = request.form['herbs_data']
        herbs_data = json.loads(herbs_data_json)

        # Create a list of herb lists from the herbs_data
        herb_lists_list = [herbs_list.split(', ') for herbs_list in herbs_data]

        print(herb_lists_list)

        # Call the search_disease function to query the database for disease information
        disease_gene_symbols = search_disease(disease_name)

        print(len(disease_gene_symbols))

        # Call the search_herb_directory function to query the database for herb information
        all_herbs_gene_symbols = []
        for herb_names_list in herb_lists_list:
            herb_names = [herb.strip() for herb in herb_names_list]
            single_herb_list_gene_symbols = search_herb_directory(herb_names)
            print(len(single_herb_list_gene_symbols))
            all_herbs_gene_symbols.append(single_herb_list_gene_symbols)

        print(len(all_herbs_gene_symbols))
        # print(all_herbs_gene_symbols)

        all_common_genes = find_common_genes(disease_gene_symbols, all_herbs_gene_symbols)

        if all_common_genes:

            all_unique_genes = find_unique_genes(all_common_genes)
            print(all_unique_genes)
            print(len(all_unique_genes))

            if all_unique_genes:
                # Call the Enrichr API to upload gene lists and perform enrichment analysis
                json_data = upload_gene_lists(all_unique_genes)
                library = 'DisGeNET'
                enrichment_data = enrichment_analysis(json_data, library)

            # Pass the enrichment_data to the results page
            return render_template('result.html', enrichment_data=enrichment_data)

    # If the method is not POST (e.g., accessing the page directly), redirect to the homepage
    return redirect(url_for('index'))


# The main entry point of the application
if __name__ == '__main__':
    app.run(debug=True)
