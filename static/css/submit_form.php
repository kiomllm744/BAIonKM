<?php
if ($_SERVER["REQUEST_METHOD"] == "POST") {
    // Get the disease name and herbs from the form data
    $diseaseName = strtolower($_POST["disease"]);
    $herbs = strtolower($_POST["herbs[]"]);

    // Explode the herbs string into an array
    $herbsArray = explode(',', $herbs);

    // Convert each herb to lowercase and trim spaces
    foreach ($herbsArray as &$herb) {
        $herb = strtolower(trim($herb));
    }
    unset($herb); // Unset the reference to the last element of the array

    // Validate the disease name and herbs (you can add more validation here)

    // Connect to the SQLite database
    $db = new SQLite3('diseaseportal.db');

    // Check if the connection was successful
    if (!$db) {
        die("Connection failed: " . $db->lastErrorMsg());
    }

    // Prepare the SQL query to retrieve gene names based on the exact disease name (case-insensitive)
    $diseaseQuery = "SELECT geneName FROM diseases WHERE LOWER(diseaseName) = :diseaseName";
    $stmt = $db->prepare($diseaseQuery);
    $stmt->bindParam(':diseaseName', $diseaseName);
    $diseaseResult = $stmt->execute();

    // Prepare the SQL query to retrieve gene names based on the herbs
    $herbsQuery = "SELECT Genes FROM herbs WHERE LOWER(herbName) IN (:herbs)";
    $stmt = $db->prepare($herbsQuery);
    $stmt->bindValue(':herbs', implode(',', $herbsArray), SQLITE3_TEXT);
    $herbsResult = $stmt->execute();

    // Check if the queries were successful
    if ($diseaseResult && $herbsResult) {
        // Fetch gene names from the results
        $diseaseGeneNames = [];
        while ($row = $diseaseResult->fetchArray(SQLITE3_ASSOC)) {
            $diseaseGeneNames[] = $row['geneName'];
        }

        $herbsGeneNames = [];
        while ($row = $herbsResult->fetchArray(SQLITE3_ASSOC)) {
            $herbsGeneNames[] = $row['geneName'];
        }

        // Close the results and statements
        $diseaseResult->finalize();
        $herbsResult->finalize();
        $stmt->close();

        // Close the database connection
        $db->close();

        // Count and display the genes connected to the disease and herbs
        $totalDiseaseGenes = count($diseaseGeneNames);
        $totalHerbsGenes = count($herbsGeneNames);

        echo "<h1>Gene Names for Disease: $diseaseName</h1>";
        echo "<p>Total Genes for Disease: $totalDiseaseGenes</p>";
        echo "<ul>";
        foreach ($diseaseGeneNames as $gene) {
            echo "<li>$gene</li>";
        }
        echo "</ul>";

        echo "<h1>Gene Names for Herbs</h1>";
        echo "<p>Total Genes for Herbs: $totalHerbsGenes</p>";
        echo "<ul>";
        foreach ($herbsGeneNames as $gene) {
            echo "<li>$gene</li>";
        }
        echo "</ul>";
    } else {
        echo "Error: " . $db->lastErrorMsg();
    }
}
?>
