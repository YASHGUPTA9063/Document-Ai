We want to make a backend having Mistral Workflow.

Workflow:
It will have multiple agents.
From the frontend we will upload a document, It will be of pdf, image, docs.
First activity will be Intake, which will take the documents which uploaded and will check there is some duplicate documents or not. If there is same name document then we will ask the user for approval to override the document.

If the document is not duplicate then we will send it next activity that is classifier.
Classifier activity will check the document type, there are multiple document types

- Invoice
- Contracts
- Medical Records
- KYC (Passport, Driving Licence)
- Bank Records
- Others

After classification, we will use next activity that is extractor, which will extract the data from the document. We wil extract the specific fields based on the document type. In the first build we will make the extractor for the invoice only.

After extractor, we will use next activity that is validator, which will validate the extracted data having some set of rules. We will use the Mistral's OCR API to extract this things and will aslo have the confidence score given by the API.
After that, we will use next activity that is Reviewer, which will have a human in the loop to review the extracted data. If the score is less then 80% then we will send it to the user for the approval. They can correct this or can approve this.
After that, we will use next activity that is Output, which will save the extracted data in the database and will send the response to the frontend.

This is the working of the MIstral Workflow. I want you to create a backend for this workflow using Mistral Workflow and main file should expose the api for the frontend using Fast API.
