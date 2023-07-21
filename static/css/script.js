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

// Add click event listeners to the buttons
addBtn.addEventListener('click', addHerbsInput);
removeBtn.addEventListener('click', removeHerbsInput);
