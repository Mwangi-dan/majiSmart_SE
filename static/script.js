function loadContent(section) {
    fetch("/" + section)
      .then((response) => response.text())
      .then((html) => {
        console.log(html);
        document.getElementById("content").innerHTML = html;
      })
      .catch((error) =>
        console.error("Error loading the section: ", error)
      );
}
