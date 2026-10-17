/** This file is used for old browsers, so DO NOT use ES6 syntax. */

var url = window.location !== window.parent.location ? document.referrer : document.location.href;

/* To prevent the clickjacking. For more details contact Xinhao */
if (self == top) {
    var is10Inches = navigator.platform === 'Linux armv7l';
    var isWebView44 = navigator.userAgent.match(/\(Linux; Android.+; rk3288.+wv\).+Chrome\/44/i) !== null;

    if (is10Inches && isWebView44) {
        window.location.replace("./update-browser/index.html?v=1.1");
    } else {
        // Everything checks out, show the page.
        document.documentElement.style.display = "block";
    }
} else if (url != "") {
    // Break out of the frame.
    top.location = self.location;
} else {
    // IE and FF go here
    document.documentElement.style.display = "none";
}
