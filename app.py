from flask import Flask, render_template


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_form():
    your_data = {
        'result1': 'Data for result 1',
        'result2': 'Data for result 2',
        'result3': 'Data for result 3'
    }
    # Your existing code for data processing here
    return render_template('result.html', data=your_data)


############ DisGeNET using Enricher API #####################

import pandas as pd
import csv
import os
import logging
import gseapy as gp
import pandas as pd
import json
import requests

# Set the display width option to a larger value
pd.set_option('display.width', 100000)
pd.set_option('display.max_colwidth', 110)
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)

logging.basicConfig(level=logging.INFO)  # Configure logging


def search_disease(csv_file, disease_name):
    try:
        with open(csv_file, 'r') as file:
            reader = csv.reader(file)
            header = next(reader)  # Read the header row

            # Find the index of the 'diseaseName' column
            diseaseName_column_index = header.index('diseaseName')
            disease_geneName_column_index = header.index('geneName')

            # Search for records matching the disease name
            matching_records = []
            disease_gene_symbols = []
            for row in reader:
                if row[diseaseName_column_index].lower() == disease_name.lower():
                    matching_records.append(row)
                    disease_gene_symbols.append(row[disease_geneName_column_index])

            print(len(matching_records))
            print(len(disease_gene_symbols))

            return matching_records, disease_gene_symbols, header

    except FileNotFoundError:
        logging.error(f"CSV file '{csv_file}' not found.")
        return [], [], []

    except csv.Error as e:
        logging.error(f"Error reading CSV file: {e}")
        return [], [], []


def search_herb_directory(directory, herb_names):
    single_herb_list_gene_symbols = []
    missing_herbs = []  # List to store missing herbs

    for herb_name in herb_names:
        herb_csv_file = os.path.join(directory, f'{herb_name}.csv')
        if os.path.isfile(herb_csv_file):
            try:
                with open(herb_csv_file, 'r') as file:
                    reader = csv.reader(file)
                    header = next(reader)  # Read the header row
                    herb_gene_symbol_index = header.index('Genes')

                    for row in reader:
                        single_herb_list_gene_symbols.append(row[herb_gene_symbol_index])

            except FileNotFoundError:
                logging.warning(f"CSV file '{herb_csv_file}' not found.")

            except csv.Error as e:
                logging.error(f"Error reading CSV file: {e}")
        else:
            missing_herbs.append(herb_name)  # Add missing herb to the list

    if missing_herbs:
        print(f"The following herbs are missing from the directory: {', '.join(missing_herbs)}")

    print(len(single_herb_list_gene_symbols))
    return single_herb_list_gene_symbols


def get_user_input(prompt):
    """Get user input with validation."""
    while True:
        user_input = input(prompt).strip()
        if user_input:
            return user_input
        else:
            print("Invalid input. Please try again.")


def prompt_another_herb_list():
    print()
    """Prompt the user if they want to input another herb list."""
    choice = get_user_input("Do you want to input another herb list? (y/n): ")
    return choice.lower() == 'y'


def display_common_genes(disease_gene_symbols, herbs_lists_list, all_herbs_gene_symbols):
    disease_gene_symbols_set = set(disease_gene_symbols)  # Keep disease_gene_symbols as strings

    all_common_genes = []  # List to store the common genes for each herb set

    for i, single_herb_list_gene_symbols in enumerate(all_herbs_gene_symbols):
        single_herb_list_gene_symbols_set = set(
            single_herb_list_gene_symbols)  # Keep single_herb_list_gene_symbols as strings

        common_genes = disease_gene_symbols_set & single_herb_list_gene_symbols_set  # Find common elements

        # Display the common genes for the current herb set
        if common_genes:
            print()
            print(f"Common Genes between Disease and Herb List {i + 1}:")
            print()
            print("Herb Names:", herbs_lists_list[i])
            print("Common Genes:", common_genes)
            print(f"Number of common genes: {len(common_genes)}")
            print()
            print()
        else:
            print(f"No common genes found between Disease and Herb List {i + 1}.")
            print()

        all_common_genes.append(common_genes)  # Add common genes to the list

    return all_common_genes


def display_unique_genes(all_common_genes):
    unique_genes = set(all_common_genes[0])  # Initialize with the genes from the first list
    all_unique_genes = []  # Main list to store unique genes for all herb lists

    # Compare with the genes from the other lists
    for common_genes in all_common_genes[1:]:
        unique_genes -= set(common_genes)

    print("Unique Genes:")
    print()
    for i, genes in enumerate(all_common_genes):
        herb_list_index = i + 1
        unique_genes_for_list = set(genes) - set().union(*all_common_genes[:i], *all_common_genes[i + 1:]) if len(
            all_common_genes) > 1 else set(genes)
        print(f"Herb List {herb_list_index}: {unique_genes_for_list}")
        print(len(unique_genes_for_list))
        all_unique_genes.append(unique_genes_for_list)  # Append unique genes to the main list

    print()
    print()

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
        print(data)
        all_data.append(data)

    return all_data


def enrichment_analysis(data_list, library):
    ENRICHR_URL = 'https://maayanlab.cloud/Enrichr/enrich'
    query_string = '?userListId=%s&backgroundType=%s'
    gene_set_library = library
    # cutoff = cutoff_value

    for data in data_list:
        user_list_id = data['userListId']
        response = requests.get(ENRICHR_URL + query_string % (user_list_id, gene_set_library))
        print(response.url)

        if not response.ok:
            raise Exception(f"Error fetching enrichment results for userListId: {user_list_id}")

        data = json.loads(response.text)
        df = pd.DataFrame(data)
        print(f"Enrichment Analysis for userListId: {user_list_id}")
        # print(df.head(15).to_string(index=False))
        # print()

        # Column names for the new DataFrame
        column_names = ['Rank', 'Term name', 'P-value', 'Z-score', 'Combined score', 'Overlapping genes',
                        'Adjusted p-value', 'Old p-value', 'Old adjusted p-value']

        # Create an empty DataFrame
        new_df = pd.DataFrame(columns=column_names)

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

                    # Append the new row to the new DataFrame
                    new_df = new_df.append(new_row, ignore_index=True)

        # Filter the new DataFrame to get only the top 15 entries with adjusted_p_value > 0.01
        filtered_df = new_df.head(30)

        # Display the filtered DataFrame
        print(filtered_df)
        print()
        print()


def main():
    # Prompt for disease name
    disease_name = get_user_input("Enter the name of the disease: ")

    # Search for disease in the CSV file
    csv_file = 'outputcsv-deduplicated.csv'
    matching_records, disease_gene_symbols, header = search_disease(csv_file, disease_name)

    if matching_records:
        print(f"Disease '{disease_name}' found in the database.")
        print()

        # Prompt for herb lists
        herb_lists_list = []
        while True:
            herb_list = get_user_input("Enter a comma-separated list of herb names (or 'stop' to stop): ")
            if herb_list.lower() == 'stop':
                break
            herb_lists_list.append(herb_list.split(','))

        if herb_lists_list:
            print()
            print(
                f"Searching for common genes between Disease '{disease_name}' and {len(herb_lists_list)} herb list(s)...")
            print()

            all_herbs_gene_symbols = []
            for herbs_list in herb_lists_list:
                herb_names = [herb.strip() for herb in herbs_list]
                directory = r'C:\Users\KIOM_User\Jupter_Projects\Batman_Project\Final_Herbs(With Gene Ids)'
                single_herb_list_gene_symbols = search_herb_directory(directory, herb_names)
                all_herbs_gene_symbols.append(single_herb_list_gene_symbols)

            all_common_genes = display_common_genes(disease_gene_symbols, herb_lists_list, all_herbs_gene_symbols)

            if all_common_genes:

                all_unique_genes = display_unique_genes(all_common_genes)

                if all_unique_genes:

                    json_data = upload_gene_lists(all_unique_genes)
                    print(json_data)
                else:
                    print("No unique genes found between the disease and any herb lists.")
                    print()

                library = 'DisGeNET'
                # cutoff = 0.5
                enrichment_analysis(json_data, library)
            else:
                print("No common genes found between the disease and any herb lists.")
                print()
        else:
            print("No herb lists provided. Exiting the program.")
            print()
    else:
        print(f"Disease '{disease_name}' not found in the database. Exiting the program.")
        print()


if __name__ == "__main__":
    main()

