async function fetchDevices() {
    try {
        let response = await fetch('/devices');
        let data = await response.json(); // ✅ Correctly extract the response
        
        if (!data.devices || !Array.isArray(data.devices)) {
            throw new Error("Invalid API response: Expected an array of devices");
        }

        let devices = data.devices;
        let container = document.getElementById('device-list');
        container.innerHTML = "";

        if (devices.length === 0) {
            container.innerHTML = "<p>No devices found.</p>";
            return;
        }

        devices.forEach(device => {
            let div = document.createElement('div');
            div.className = "device";
            div.innerHTML = `<h3>${device.device_name} (${device.device_id})</h3>
                             <button onclick="controlDevice('${device.device_id}', 'ON')">ON</button>
                             <button onclick="controlDevice('${device.device_id}', 'OFF')">OFF</button>`;
            container.appendChild(div);
        });
    } catch (error) {
        console.error("❌ Error fetching devices:", error);
        document.getElementById('device-list').innerHTML = "<p style='color: red;'>Error loading devices.</p>";
    }
}

async function controlDevice(device_id, status) {
    try {
        let response = await fetch(`/device/${device_id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: status })
        });

        let result = await response.json();

        if (response.ok) {
            alert(result.message || `Device ${device_id} updated to ${status}`);
            fetchDevices(); // Refresh device list after update
        } else {
            throw new Error(result.error || "Failed to update device status.");
        }
    } catch (error) {
        console.error("❌ Error controlling device:", error);
        alert(`Failed to update device ${device_id}.`);
    }
}

// ✅ Load devices on page load
document.addEventListener("DOMContentLoaded", fetchDevices);
