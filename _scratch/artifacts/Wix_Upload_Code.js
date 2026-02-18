// Wix Code for File Upload Integration
// Add this to your Wix page's code panel (Developer Tools -> Code Files)

import { fetch } from 'wix-fetch';

// REPLACE THIS with your Power Automate HTTP URL after creating the flow
const POWER_AUTOMATE_URL = 'YOUR_HTTP_TRIGGER_URL_HERE';

$w.onReady(function () {

    // Handle file upload button change event
    $w("#uploadButton").onChange(async (event) => {
        if (event.target.value.length > 0) {

            // Show loading state
            $w("#uploadButton").disable();
            $w("#statusMessage").text = "Uploading...";

            const file = event.target.value[0];

            // Validate email and name
            const fullName = $w("#fullNameInput").value;
            const email = $w("#emailInput").value;

            if (!fullName || !email) {
                $w("#statusMessage").text = "Please fill in your name and email";
                $w("#uploadButton").enable();
                return;
            }

            if (!email.includes('@')) {
                $w("#statusMessage").text = "Please enter a valid email";
                $w("#uploadButton").enable();
                return;
            }

            try {
                // Convert file to base64
                const base64Content = await fileToBase64(file);

                // Send to Power Automate
                const response = await fetch(POWER_AUTOMATE_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        fileName: file.name,
                        fileContent: base64Content,
                        fullName: fullName,
                        email: email
                    })
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    $w("#statusMessage").text = `✓ File uploaded successfully! Ticket: ${result.ticketNumber}`;
                    $w("#statusMessage").style.color = "#4CAF50";

                    // Clear form
                    $w("#fullNameInput").value = "";
                    $w("#emailInput").value = "";
                    $w("#uploadButton").reset();
                } else {
                    throw new Error(result.message || 'Upload failed');
                }

            } catch (error) {
                $w("#statusMessage").text = `✗ Upload failed: ${error.message}`;
                $w("#statusMessage").style.color = "#F44336";
            } finally {
                $w("#uploadButton").enable();
            }
        }
    });
});

// Helper function to convert file to base64
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // Remove the data URL prefix (e.g., "data:image/png;base64,")
            const base64String = reader.result.split(',')[1];
            resolve(base64String);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}
