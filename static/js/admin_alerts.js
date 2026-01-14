fetch("/admin/alerts")
  .then(response => response.json())
  .then(data => {
      const tbody = document.getElementById("alerts-body");
      tbody.innerHTML = "";

      data.forEach(alert => {
          const row = document.createElement("tr");

          row.innerHTML = `
              <td>${alert.created_at}</td>
              <td><span class="badge ${alert.severity}">${alert.severity}</span></td>
              <td>${alert.source}</td>
              <td>${alert.message}</td>
              <td>${alert.status}</td>
          `;

          tbody.appendChild(row);
      });
  })
  .catch(err => {
      console.error("Error loading alerts:", err);
  });
