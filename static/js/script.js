let lastActivityCount = 0;

setInterval(async () => {
    const healthResponse = await fetch('/api/health');
    const healthData = await healthResponse.json();
    const activityResponse = await fetch('/api/activity');
    const activityData = await activityResponse.json();

    // Update Health Data
    const healthList = document.getElementById('health-data');
    healthList.innerHTML = '';
    healthData.forEach(entry => {
        const li = document.createElement('li');
        li.className = entry['heart_rate'] > 100 || entry['glucose'] > 130 ? 'bg-red-100 dark:bg-red-900 p-3 rounded-lg' : 
                       entry['heart_rate'] > 90 ? 'bg-yellow-100 dark:bg-yellow-900 p-3 rounded-lg' : 'bg-green-100 dark:bg-green-900 p-3 rounded-lg';
        li.innerHTML = `<span class="font-medium text-gray-800 dark:text-gray-200">${entry['timestamp']}</span> - 
                        Heart Rate: <span class="font-bold text-gray-900 dark:text-gray-100">${entry['heart_rate']}</span> bpm, 
                        BP: <span class="font-bold text-gray-900 dark:text-gray-100">${entry['blood_pressure']}</span>, 
                        Glucose: <span class="font-bold text-gray-900 dark:text-gray-100">${entry['glucose']}</span> mg/dL${
                            entry['event'] ? `<span class="text-red-600 dark:text-red-400 font-bold ml-2"> - ${entry['event']}</span>` : ''
                        }`;
        healthList.appendChild(li);
    });

    // Update Activity Log
    const activityList = document.getElementById('activity-log');
    const filter = document.getElementById('filter').value;
    activityList.innerHTML = '';
    const filteredData = activityData.filter(entry => {
        if (filter === 'alert') return entry['activity'].includes('Alert');
        if (filter === 'reminder') return entry['activity'].includes('Reminder');
        return true;
    });
    filteredData.forEach(entry => {
        const li = document.createElement('li');
        li.className = entry['activity'].includes('Alert') ? 
                       (entry['activity'].includes('Critical') ? 'bg-red-100 dark:bg-red-900 p-3 rounded-lg flex items-center' : 'bg-yellow-100 dark:bg-yellow-900 p-3 rounded-lg flex items-center') : 
                       'bg-gray-100 dark:bg-gray-900 p-3 rounded-lg flex items-center';
        li.innerHTML = `<i class="${entry['activity'].includes('Alert') ? 'fas fa-exclamation-circle text-red-500' : entry['activity'].includes('Reminder') ? 'fas fa-bell text-blue-500' : 'fas fa-info-circle text-gray-500'} mr-2"></i>
                        <span class="font-medium text-gray-800 dark:text-gray-200">${entry['timestamp']}</span> - 
                        <span class="font-bold text-gray-900 dark:text-gray-100">${entry['activity']}</span>`;
        activityList.appendChild(li);
    });

    // Show Alert Popup for New Alerts
    const newActivityCount = activityData.length;
    if (newActivityCount > lastActivityCount) {
        const latestActivity = activityData[activityData.length - 1];
        if (latestActivity['activity'].includes('Alert')) {
            const alertPopup = document.getElementById('alert-popup');
            const alertMessage = document.getElementById('alert-message');
            alertMessage.textContent = latestActivity['activity'];
            alertPopup.classList.remove('hidden');
        }
    }
    lastActivityCount = newActivityCount;
}, 10000);

// Filter on Change
document.getElementById('filter').addEventListener('change', async () => {
    const activityResponse = await fetch('/api/activity');
    const activityData = await activityResponse.json();
    const activityList = document.getElementById('activity-log');
    const filter = document.getElementById('filter').value;
    activityList.innerHTML = '';
    const filteredData = activityData.filter(entry => {
        if (filter === 'alert') return entry['activity'].includes('Alert');
        if (filter === 'reminder') return entry['activity'].includes('Reminder');
        return true;
    });
    filteredData.forEach(entry => {
        const li = document.createElement('li');
        li.className = entry['activity'].includes('Alert') ? 
                       (entry['activity'].includes('Critical') ? 'bg-red-100 dark:bg-red-900 p-3 rounded-lg flex items-center' : 'bg-yellow-100 dark:bg-yellow-900 p-3 rounded-lg flex items-center') : 
                       'bg-gray-100 dark:bg-gray-900 p-3 rounded-lg flex items-center';
        li.innerHTML = `<i class="${entry['activity'].includes('Alert') ? 'fas fa-exclamation-circle text-red-500' : entry['activity'].includes('Reminder') ? 'fas fa-bell text-blue-500' : 'fas fa-info-circle text-gray-500'} mr-2"></i>
                        <span class="font-medium text-gray-800 dark:text-gray-200">${entry['timestamp']}</span> - 
                        <span class="font-bold text-gray-900 dark:text-gray-100">${entry['activity']}</span>`;
        activityList.appendChild(li);
    });
});