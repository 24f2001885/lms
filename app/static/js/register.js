/**
 * Registration form interactive enhancements.
 * Toggles the Examiner Information section based on the selected role radio button.
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var examinerFields = document.getElementById("examiner-fields");
    var roleRadios = document.querySelectorAll('input[name="role"]');
    if (!examinerFields || !roleRadios.length) return;

    function toggleExaminerFields() {
      var checkedRadio = document.querySelector('input[name="role"]:checked');
      if (checkedRadio && checkedRadio.value === "examiner") {
        examinerFields.style.display = "block";
      } else {
        examinerFields.style.display = "none";
      }
    }

    Array.prototype.forEach.call(roleRadios, function (radio) {
      radio.addEventListener("change", toggleExaminerFields);
    });

    toggleExaminerFields();
  });
})();
