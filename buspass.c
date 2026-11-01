#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX 100

struct Student
{
    int age;
    char studentID[20];
    char name[50];
    char college[100];
    char course[50];
    char year[30];
    char mobile[15];
    char source[50];
    char destination[50];
    char status[10];
    char validity[15];
};

// copy text into a struct field without overflow
// also removes the | symbol so the file format stays correct
void setText(char *field, int size, char *value)
{
    int i;

    if (value == NULL)
    {
        value = "";
    }

    strncpy(field, value, size - 1);
    field[size - 1] = '\0';

    for (i = 0; field[i] != '\0'; i++)
    {
        if (field[i] == '|')
        {
            field[i] = ' ';
        }
    }
}

// get the next part of a line split by |
char *nextPart()
{
    char *part = strtok(NULL, "|");

    if (part == NULL)
    {
        return "";
    }

    return part;
}

// read all students from students.txt and return how many
// one line in the file looks like:
// STU1001|Name|20|College|Course|Year|Mobile|Source|Destination|Active|3 Months
int loadStudents(struct Student list[])
{
    int count = 0;
    char line[600];
    FILE *fp = fopen("students.txt", "r");

    if (fp == NULL)
    {
        return 0; // no file yet, so no students yet
    }

    while (fgets(line, sizeof(line), fp) != NULL && count < MAX)
    {
        line[strcspn(line, "\n")] = '\0';

        if (line[0] == '\0')
        {
            continue;
        }

        setText(list[count].studentID, sizeof(list[count].studentID), strtok(line, "|"));
        setText(list[count].name, sizeof(list[count].name), nextPart());
        list[count].age = atoi(nextPart());
        setText(list[count].college, sizeof(list[count].college), nextPart());
        setText(list[count].course, sizeof(list[count].course), nextPart());
        setText(list[count].year, sizeof(list[count].year), nextPart());
        setText(list[count].mobile, sizeof(list[count].mobile), nextPart());
        setText(list[count].source, sizeof(list[count].source), nextPart());
        setText(list[count].destination, sizeof(list[count].destination), nextPart());
        setText(list[count].status, sizeof(list[count].status), nextPart());
        setText(list[count].validity, sizeof(list[count].validity), nextPart());
        count++;
    }

    fclose(fp);
    return count;
}

// write all the students back to students.txt
void saveStudents(struct Student list[], int count)
{
    int i;
    FILE *fp = fopen("students.txt", "w");

    if (fp == NULL)
    {
        printf("\nError: Cannot open students.txt\n");
        return;
    }

    for (i = 0; i < count; i++)
    {
        fprintf(fp, "%s|%s|%d|%s|%s|%s|%s|%s|%s|%s|%s\n",
                list[i].studentID, list[i].name, list[i].age, list[i].college,
                list[i].course, list[i].year, list[i].mobile, list[i].source,
                list[i].destination, list[i].status, list[i].validity);
    }

    fclose(fp);
}

void viewStudentDetails(struct Student *s)
{
    printf("\n====================================\n");
    printf("        STUDENT DETAILS\n");
    printf("====================================\n");

    printf("Student ID  : %s\n", s->studentID);
    printf("Name        : %s\n", s->name);
    printf("Age         : %d\n", s->age);
    printf("College     : %s\n", s->college);
    printf("Course      : %s\n", s->course);
    printf("Year        : %s\n", s->year);
    printf("Mobile      : %s\n", s->mobile);
    printf("Source      : %s\n", s->source);
    printf("Destination : %s\n", s->destination);
    printf("Status      : %s\n", s->status);
    printf("Validity    : %s\n", s->validity);

    printf("====================================\n");
}

// register a new student using the values sent by the web page
void registerStudent(struct Student *s, struct Student list[], int count, char *args[])
{
    int i;
    int id = 1001;
    FILE *fp;

    if (count >= MAX)
    {
        printf("\nSorry, Student Limit Reached!\n");
        return;
    }

    // find the biggest ID so IDs never repeat after closing the program
    for (i = 0; i < count; i++)
    {
        int num = atoi(&list[i].studentID[3]); // skip the "STU" part
        if (num >= id)
        {
            id = num + 1;
        }
    }

    printf("\n===== STUDENT REGISTRATION =====\n");

    setText(s->name, sizeof(s->name), args[2]);
    s->age = atoi(args[3]);
    setText(s->college, sizeof(s->college), args[4]);
    setText(s->course, sizeof(s->course), args[5]);
    setText(s->year, sizeof(s->year), args[6]);
    setText(s->mobile, sizeof(s->mobile), args[7]);
    setText(s->source, sizeof(s->source), args[8]);
    setText(s->destination, sizeof(s->destination), args[9]);

    sprintf(s->studentID, "STU%d", id);
    setText(s->status, sizeof(s->status), "Active");
    setText(s->validity, sizeof(s->validity), "3 Months");

    // append mode so the old students are not lost
    fp = fopen("students.txt", "a");
    if (fp == NULL)
    {
        printf("\nError: Cannot open students.txt\n");
        return;
    }

    fprintf(fp, "%s|%s|%d|%s|%s|%s|%s|%s|%s|%s|%s\n",
            s->studentID, s->name, s->age, s->college, s->course, s->year,
            s->mobile, s->source, s->destination, s->status, s->validity);
    fclose(fp);

    printf("\nREGISTRATION SUCCESSFUL!\n");
    printf("Student ID: %s\n", s->studentID);
    viewStudentDetails(s);
}

// find a student by Student ID, return position or -1 if not found
int findStudent(struct Student list[], int count, char *id)
{
    int i;

    for (i = 0; i < count; i++)
    {
        if (strcmp(list[i].studentID, id) == 0)
        {
            return i;
        }
    }

    return -1;
}

int main(int argc, char *argv[])
{
    struct Student list[MAX];
    struct Student s;
    int count = loadStudents(list);

    printf("\n========================================\n");
    printf("       BUS PASS MANAGEMENT SYSTEM       \n");
    printf("========================================\n");

    if (argc < 2)
    {
        printf("\nUsage:\n");
        printf("buspass register <name> <age> <college> <course> <year> <mobile> <source> <destination>\n");
        printf("buspass search <StudentID or Name>\n");
        printf("buspass renew <StudentID> <months>\n");
        printf("buspass cancel <StudentID>\n");
        return 1;
    }

    if (strcmp(argv[1], "register") == 0)
    {
        if (argc != 10)
        {
            printf("\nError: register needs 8 values!\n");
            return 1;
        }

        registerStudent(&s, list, count, argv);
        return 0;
    }

    if (strcmp(argv[1], "search") == 0)
    {
        int i;
        int found = 0;

        if (argc != 3)
        {
            printf("\nError: search needs a Student ID or name!\n");
            return 1;
        }

        printf("\n===== STUDENT SEARCH =====\n");

        // loop through all students and show the ones that match
        for (i = 0; i < count; i++)
        {
            int idMatch = strcmp(argv[2], list[i].studentID) == 0;
            int nameMatch = list[i].name[0] != '\0' && strstr(list[i].name, argv[2]) != NULL;

            if (idMatch || nameMatch)
            {
                viewStudentDetails(&list[i]);
                found = 1;
            }
        }

        if (found == 0)
        {
            printf("\nNo Student Found!\n");
        }
        return 0;
    }

    if (strcmp(argv[1], "renew") == 0)
    {
        int index;
        int months;

        if (argc != 4)
        {
            printf("\nError: renew needs a Student ID and months!\n");
            return 1;
        }

        index = findStudent(list, count, argv[2]);
        if (index == -1)
        {
            printf("\nNo Student Found with ID %s!\n", argv[2]);
            return 1;
        }

        months = atoi(argv[3]);
        if (months <= 0)
        {
            printf("\nError: months must be a number bigger than 0!\n");
            return 1;
        }

        if (strcmp(list[index].status, "Cancelled") == 0)
        {
            printf("\nThis Bus Pass is Already Cancelled!\n");
            return 1;
        }

        // update the validity and write the whole file back
        sprintf(list[index].validity, "%d Months", months);
        saveStudents(list, count);

        printf("\nBUS PASS RENEWED FOR %d MONTHS!\n", months);
        viewStudentDetails(&list[index]);
        return 0;
    }

    if (strcmp(argv[1], "cancel") == 0)
    {
        int index;

        if (argc != 3)
        {
            printf("\nError: cancel needs a Student ID!\n");
            return 1;
        }

        index = findStudent(list, count, argv[2]);
        if (index == -1)
        {
            printf("\nNo Student Found with ID %s!\n", argv[2]);
            return 1;
        }

        if (strcmp(list[index].status, "Cancelled") == 0)
        {
            printf("\nThis Bus Pass is Already Cancelled!\n");
            return 1;
        }

        // mark the pass as cancelled and write the file back
        setText(list[index].status, sizeof(list[index].status), "Cancelled");
        saveStudents(list, count);

        printf("\nBUS PASS CANCELLED!\n");
        printf("Student ID: %s\n", list[index].studentID);
        printf("Name: %s\n", list[index].name);
        return 0;
    }

    printf("\nInvalid Command! Use register, search, renew or cancel.\n");
    return 1;
}
