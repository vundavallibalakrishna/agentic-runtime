"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { FormNote, SampleForm } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";

/** Renders every base component so the catalogue stays referenced. */
export function UiGallery() {
  return (
    <Card>
      <Badge>draft</Badge>
      <Input aria-label="Search" placeholder="Search" />
      <Button type="button">Save</Button>
      <Skeleton className="h-4 w-24" />
      <Dialog>
        <DialogTrigger>
          <Button type="button" variant="outline">
            Open
          </Button>
        </DialogTrigger>
        <DialogContent title="Confirm">Ready</DialogContent>
      </Dialog>
      <Sheet title="Details" trigger="Details">
        Panel
      </Sheet>
      <DropdownMenu label="More">
        <DropdownMenuItem>Rename</DropdownMenuItem>
      </DropdownMenu>
      <Tabs defaultValue="one">
        <TabsList>
          <TabsTrigger value="one">One</TabsTrigger>
        </TabsList>
        <TabsContent value="one">First</TabsContent>
      </Tabs>
      <Tooltip label="Hint">
        <Button type="button" variant="outline">
          Hint
        </Button>
      </Tooltip>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Helpdesk</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <SampleForm />
      <FormNote>Drafts save when the API exists.</FormNote>
    </Card>
  );
}
