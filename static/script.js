// Variables to keep track of the herbs input count
let herbsCount = 1;
const maxHerbsCount = 3;

// Get the add and remove buttons
const addBtn = document.getElementById('add-btn');
const removeBtn = document.getElementById('remove-btn');

// Get the herbs container
const herbsContainer = document.querySelector('.herbs-container');

// Function to add a herbs input field
function addHerbsInput() {
    if (herbsCount >= maxHerbsCount) {
        alert('You can only input a maximum of three prescriptions.');
        return;
    }

    herbsCount++;

    const newHerbsInput = document.createElement('input');
    newHerbsInput.type = 'text';
    newHerbsInput.name = 'herbs[]'; // Note the square brackets to handle multiple values
    newHerbsInput.placeholder = 'Enter the herbs';
    newHerbsInput.required = true;
    newHerbsInput.className = 'herbs-input';

    // Create a div to wrap the new herb input
    const herbInputWrapper = document.createElement('div');
    herbInputWrapper.className = 'herbs-container '; // Add a class to style the spacing

    herbInputWrapper.appendChild(newHerbsInput);
    herbsContainer.appendChild(herbInputWrapper);
}

// Function to remove the last herbs input field
function removeHerbsInput() {
    if (herbsCount === 1) {
        alert('You must have at least one prescription input.');
        return;
    }

    const lastHerbsInputWrapper = herbsContainer.lastElementChild;
    herbsContainer.removeChild(lastHerbsInputWrapper);
    herbsCount--;
}

// Function to collect the user's input into a list of lists of herbs
function collectHerbsData() {
    const herbInputs = document.querySelectorAll('.herbs-input');
    const herbsLists = Array.from(herbInputs).map(input => input.value);
    return herbsLists;
}


// Add click event listeners to the buttons
addBtn.addEventListener('click', addHerbsInput);
removeBtn.addEventListener('click', removeHerbsInput);

// Add a submit event listener to the form
const form = document.querySelector('form');
form.addEventListener('submit', (event) => {
    // Stop the form submission to handle it manually
    event.preventDefault();

    // Collect the user's input into a list of lists of herbs
    const herbsData = collectHerbsData();

    // Update the value of the existing hidden input field with the collected data
    document.getElementById('herbs-data-input').value = JSON.stringify(herbsData);


    // --- Start of added code ---
    // Print the data on the console before submitting the form
    console.log('Collected Herbs Data:');
    console.log(herbsData);
    // --- End of added code ---

    // Submit the form
    form.submit();
});
